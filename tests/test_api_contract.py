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

def test_save_qr_surfaces_network_reason(client: TestClient, monkeypatch):
    """连不上社区域名时要告诉用户真实原因，而不是「请检查账号及登录状态」。"""

    from app.api import community
    from app.services.community_dns import CommunityConnectionError

    async def boom(*_args, **_kwargs):
        raise CommunityConnectionError(
            "本机 DNS 把 zonai.skland.com 解析到 198.18.0.170，这是代理 TUN 的 Fake-IP",
        )

    monkeypatch.setattr(community.login, "save_qr", boom)
    response = client.post(
        "/api/login/skland/qr/save",
        json={"account_uid": "x", "cookie": "", "scan_code": "code"},
    )
    assert response.status_code == 400
    message = response.json()["message"]
    assert "Fake-IP" in message
    assert "请检查账号及登录状态" not in message


def test_cookie_fetch_surfaces_authkey_reason(client: TestClient, monkeypatch):
    """Cookie 换 authkey 失败要回真实原因，但不能带出 Cookie 里的凭据片段。"""

    from app.core import gacha as gacha_core
    from app.tools.gacha_mihoyo_authkey import GachaAuthkeyError

    async def unauthorized(*_args, **_kwargs):
        raise GachaAuthkeyError(
            "米游社拒绝了换取抽卡 authkey 的请求（登录已失效）：请先在「游戏签到 → 米游社」重新扫码登录"
        )

    monkeypatch.setattr(gacha_core, "fetch_mihoyo_by_cookie", unauthorized)
    response = client.post(
        "/api/gacha/fetch-cookie",
        json={
            "game": "genshin",
            "playerUid": "100000001",
            "cookie": "stuid=1; stoken=supersecrettoken",
        },
    )
    assert response.status_code == 400
    message = response.json()["message"]
    assert "登录已失效" in message
    assert "supersecrettoken" not in message
    assert "input_value" not in message and "validation error" not in message


def test_cookie_fetch_masks_unexpected_failure(client: TestClient, monkeypatch):
    """非协议层异常一律换成固定文案，内部细节（可能含凭据）不得外泄。"""

    from app.core import gacha as gacha_core

    async def boom(*_args, **_kwargs):
        raise ValueError("Cookie: stoken=supersecrettoken")

    monkeypatch.setattr(gacha_core, "fetch_mihoyo_by_cookie", boom)
    response = client.post(
        "/api/gacha/fetch-cookie",
        json={"game": "starrail", "playerUid": "100000002"},
    )
    assert response.status_code == 400
    message = response.json()["message"]
    # 中间件会在后面补请求编号，这里只锁前缀。
    assert message.startswith("记录读取未完成，请检查游戏 UID 与所选账号")
    assert "supersecrettoken" not in message


def test_cookie_fetch_operation_is_declared(tmp_path: Path):
    """生成的前端客户端要能拿到这个端点，且只强制 game 与 playerUid。"""

    spec = create_app(data_dir=tmp_path, start_scheduler=False).openapi()
    operation = spec["paths"]["/api/gacha/fetch-cookie"]["post"]
    assert operation["operationId"] == "fetchGachaRecordsByCookie"
    reference = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert reference.endswith("/GachaCookieFetchIn")
    model = spec["components"]["schemas"]["GachaCookieFetchIn"]
    assert set(model["required"]) == {"game", "playerUid"}

def test_heybox_import_forwards_arguments(client: TestClient, monkeypatch):
    """粘贴的小黑盒响应原样交给核心层，结果与跳过的卡池都要回给前端。"""

    from app.core import gacha as gacha_core

    captured: dict[str, str] = {}

    async def fake_import(game: str, heybox_id: str, player_uid: str, payload: str):
        captured.update(
            game=game, heybox_id=heybox_id, player_uid=player_uid, payload=payload
        )
        return 60, 0, ["武器池按池名对齐"], ["未导入『重构寻访』：重构寻访"]

    monkeypatch.setattr(gacha_core, "import_heybox", fake_import)
    response = client.post(
        "/api/gacha/heybox",
        json={
            "heyboxId": "123456",
            "playerUid": "102819197",
            "payload": '{"status":"ok"}',
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["added"], body["replaced"]) == (60, 0)
    assert body["warnings"] == ["武器池按池名对齐"]
    assert body["skipped"] == ["未导入『重构寻访』：重构寻访"]
    assert body["status"] == "partial"
    assert captured == {
        "game": "endfield",
        "heybox_id": "123456",
        "player_uid": "102819197",
        "payload": '{"status":"ok"}',
    }


def test_heybox_validation_failure_is_shown_to_user(client: TestClient, monkeypatch):
    """协议层文案只描述规则，可以原样回显；内部异常必须换成固定文案。"""

    from app.core import gacha as gacha_core
    from app.tools.gacha_heybox import HeyboxError

    async def mismatch(*_args, **_kwargs):
        raise HeyboxError("小黑盒数据里的游戏 UID 与填写的 UID 不一致，不能导入别人的记录")

    monkeypatch.setattr(gacha_core, "import_heybox", mismatch)
    response = client.post(
        "/api/gacha/heybox",
        json={"heyboxId": "123456", "playerUid": "102819197", "payload": "{}"},
    )
    assert response.status_code == 400
    assert "不能导入别人的记录" in response.json()["message"]

    async def boom(*_args, **_kwargs):
        raise RuntimeError("overview raw payload=supersecret")

    monkeypatch.setattr(gacha_core, "import_heybox", boom)
    response = client.post(
        "/api/gacha/heybox",
        json={"heyboxId": "123456", "playerUid": "102819197", "payload": "{}"},
    )
    assert response.status_code == 400
    message = response.json()["message"]
    assert message.startswith("小黑盒数据未导入")
    assert "supersecret" not in message


def test_heybox_revoke_reports_removed_rows(client: TestClient, monkeypatch):
    """撤销走查询参数，回包里说明删掉了多少条补录行。"""

    from app.core import gacha as gacha_core

    captured: dict[str, str] = {}

    async def fake_revoke(player_uid: str, game: str = "endfield") -> int:
        captured.update(player_uid=player_uid, game=game)
        return 59

    monkeypatch.setattr(gacha_core, "revoke_heybox", fake_revoke)
    response = client.request(
        "DELETE", "/api/gacha/heybox", params={"playerUid": "102819197"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["added"] == 0
    assert body["warnings"] == []
    assert body["message"] == "已撤销 59 条小黑盒补录记录"
    assert body["status"] == "success"
    assert captured == {"player_uid": "102819197", "game": "endfield"}


def test_heybox_operations_are_declared(tmp_path: Path):
    """生成的前端客户端要拿到这两个端点；撤销只强制 playerUid。"""

    spec = create_app(data_dir=tmp_path, start_scheduler=False).openapi()
    import_operation = spec["paths"]["/api/gacha/heybox"]["post"]
    assert import_operation["operationId"] == "importGachaHeybox"
    reference = import_operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert reference.endswith("/GachaHeyboxIn")
    model = spec["components"]["schemas"]["GachaHeyboxIn"]
    assert set(model["required"]) == {"heyboxId", "playerUid", "payload"}

    revoke = spec["paths"]["/api/gacha/heybox"]["delete"]
    assert revoke["operationId"] == "revokeGachaHeybox"
    parameters = {item["name"]: item for item in revoke["parameters"]}
    assert parameters["playerUid"]["required"] is True
    assert parameters["game"]["required"] is False
