"""HTTP 契约层测试：入参边界、错误语义与内部异常不外泄。

只做离线校验：应用用临时数据目录启动，不触发签到、不访问网络、不读真实账号。
"""

import tempfile
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models.config import AccountData
from app.models.schema import CloudSyncIn, GameSignAccountGroupConfig


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with tempfile.TemporaryDirectory() as raw_dir:
        application = create_app(data_dir=Path(raw_dir), start_scheduler=False)
        with TestClient(application, base_url="http://127.0.0.1") as test_client:
            test_client.headers.update(
                {"x-community-session": application.state.session_key}
            )
            yield test_client


def _account_name_limit() -> int:
    field = GameSignAccountGroupConfig.model_fields["Name"]
    limits = [item.max_length for item in field.metadata if hasattr(item, "max_length")]
    assert limits, "账号组名称请求模型缺少长度上限，超长名称会漏到核心层校验"
    return limits[0]


def test_account_name_limit_matches_storage_model():
    """请求模型与存储模型的上限必须相同，否则超长输入会绕过请求校验。"""

    storage_limits = [
        item.max_length
        for item in AccountData.model_fields["Name"].metadata
        if hasattr(item, "max_length")
    ]
    assert _account_name_limit() == storage_limits[0]


def test_account_update_rejects_too_long_name_without_internal_text(client: TestClient):
    uid = client.post("/api/accounts").json()["data"]["uid"]
    response = client.post(
        "/api/accounts/update",
        json={"accountId": uid, "data": {"Name": "x" * 81}},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == 422
    assert body["status"] == "error"
    # pydantic 原文（模型名、字段路径、回显入参）不得出现在错误体里。
    assert "validation error" not in body["message"]
    assert "AccountData" not in body["message"]
    assert "input_value" not in body["message"]
    assert "x" * 20 not in body["message"]

    # 上限之内仍然可以保存，证明拒绝的是超长而不是整个字段。
    accepted = client.post(
        "/api/accounts/update",
        json={"accountId": uid, "data": {"Name": "x" * 80}},
    )
    assert accepted.status_code == 200


def test_internal_validation_error_is_not_echoed(client: TestClient, monkeypatch):
    """端点内部抛出的 pydantic 校验失败不能按业务错误回显原文。"""

    from app.core import accounts as accounts_core

    async def broken_update(*_args, **_kwargs):
        AccountData.model_validate({"Name": "y" * 81})

    monkeypatch.setattr(accounts_core, "update_account", broken_update)
    uid = client.post("/api/accounts").json()["data"]["uid"]
    response = client.post(
        "/api/accounts/update",
        json={"accountId": uid, "data": {"Name": "合法名称"}},
    )
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == 500
    assert body["status"] == "error"
    assert "validation error" not in body["message"]
    assert "AccountData" not in body["message"]
    assert "日志编号" in body["message"]


def test_cloud_sync_only_accepts_credential_fields(client: TestClient, monkeypatch):
    """tokens 的键来自请求体，不能覆盖 Enabled、Name 这类非凭据字段。"""

    import app.api.cloud as cloud_api

    captured: dict[str, object] = {}

    async def fake_sign_in(*, force: bool, override_state):
        captured["state"] = override_state
        return []

    monkeypatch.setattr(cloud_api, "run_community_sign_in", fake_sign_in)
    response = client.post(
        "/api/cloud/sync",
        json={
            "accounts": [
                {
                    "uid": "uid-1",
                    "name": "云端账号",
                    "enabled": False,
                    "tokens": {
                        "Enabled": "true",
                        "Name": "被覆盖的名称",
                        "LastSignDate": "2000-01-01",
                        "MiyousheToken": "token-value",
                        "MiyousheDeviceId": "device-value",
                    },
                }
            ]
        },
    )
    assert response.status_code == 200
    state = captured["state"]
    account = state.data.accounts["uid-1"]
    assert account.Enabled is False
    assert account.Name == "云端账号"
    assert account.LastSignDate == ""
    assert account.MiyousheToken == "token-value"
    # 凭据类字段（含设备 ID）仍需透传，白名单不能收得比契约更窄。
    assert account.MiyousheDeviceId == "device-value"


def test_cloud_sync_rejects_oversized_account_list(client: TestClient):
    field = CloudSyncIn.model_fields["accounts"]
    limits = [item.max_length for item in field.metadata if hasattr(item, "max_length")]
    assert limits, "云端同步账号列表缺少上限"
    accounts = [
        {"uid": f"uid-{index}", "tokens": {}} for index in range(limits[0] + 1)
    ]
    response = client.post("/api/cloud/sync", json={"accounts": accounts})
    assert response.status_code == 422
    assert response.json()["code"] == 422
    assert "validation error" not in response.json()["message"]


def test_gacha_import_reports_partial_when_warnings(client: TestClient, monkeypatch):
    """导入与抓取返回同一个模型，部分成功时的 status 必须一致。"""

    from app.core import gacha as gacha_core

    async def fake_import(*_args, **_kwargs):
        return 3, 5, ["2 条记录字段不完整，已跳过"]

    monkeypatch.setattr(gacha_core, "import_records", fake_import)
    response = client.post("/api/gacha/import", json={"game": "genshin", "payload": "{}"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["warnings"] == ["2 条记录字段不完整，已跳过"]


def test_every_operation_declares_unique_operation_id(tmp_path: Path):
    spec = create_app(data_dir=tmp_path, start_scheduler=False).openapi()
    operations = [
        operation
        for path_item in spec["paths"].values()
        for operation in path_item.values()
    ]
    identifiers = [
        operation["operationId"] for operation in operations if "operationId" in operation
    ]
    assert len(identifiers) == len(operations)
    assert len(identifiers) == len(set(identifiers))

def test_activity_query_forwards_refresh_flag(client: TestClient, monkeypatch):
    """手动刷新必须把 refresh 透到核心层；不传时默认走缓存。"""

    from app.core.runtime import runtime as core_runtime

    calls: list[dict] = []

    async def fake_activity(account_ids=None, *, refresh: bool = False):
        calls.append({"ids": account_ids, "refresh": refresh})
        return []

    monkeypatch.setattr(core_runtime, "activity", fake_activity)
    assert client.post("/api/activity", json={}).status_code == 200
    assert calls[-1] == {"ids": None, "refresh": False}
    assert client.post("/api/activity", json={"refresh": True}).status_code == 200
    assert calls[-1] == {"ids": None, "refresh": True}
