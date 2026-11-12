"""森空岛扫码全链路回归：临时账号、假上游，不使用真实网络或凭据。"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.state import state
from app.main import create_app
from app.services.community_dns import CommunityConnectionError
from app.services.network import network
from app.tools import skland


@pytest.fixture()
def qr_client(tmp_path, monkeypatch):
    monkeypatch.setattr(skland, "_cached_device_id", None)
    monkeypatch.setattr(skland, "_cache_time", None)
    monkeypatch.setattr(skland, "_server_clock", None)
    application = create_app(data_dir=tmp_path, start_scheduler=False)
    with TestClient(application, base_url="http://127.0.0.1") as client:
        client.headers["x-community-session"] = application.state.session_key
        yield client


def _install_upstream(monkeypatch, handler):
    monkeypatch.setattr(
        network, "transport_factory", lambda: httpx.MockTransport(handler)
    )


def test_create_does_not_depend_on_device_verification(qr_client, monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        # 设备服务故障也应能生成二维码；调用它就让用例失败。
        assert str(request.url) == skland.SKLAND_SCAN_CREATE_URL
        assert request.method == "POST"
        assert "did" not in request.headers
        assert json.loads(request.content) == {}
        return httpx.Response(
            200,
            json={
                "status": 0,
                "data": {
                    "scanId": "fake-ticket",
                    "scanUrl": "https://example.invalid/scan",
                },
            },
        )

    _install_upstream(monkeypatch, handler)
    response = qr_client.post("/api/login/skland/qr/create")
    assert response.status_code == 200
    result = response.json()
    assert result["ticket"] == "fake-ticket"
    assert result["qr_url"] == "https://example.invalid/scan"
    assert result["device"]
    assert len(requests) == 1
    assert skland._cached_device_id is None


@pytest.mark.parametrize("data", [None, {}, {"scanId": {}, "scanUrl": ["invalid"]}])
def test_create_rejects_malformed_qr(qr_client, monkeypatch, data):
    _install_upstream(
        monkeypatch, lambda _: httpx.Response(200, json={"status": 0, "data": data})
    )
    response = qr_client.post("/api/login/skland/qr/create")
    assert response.status_code == 400
    assert not response.json().get("qr_url")


@pytest.mark.parametrize(
    ("stage", "body"),
    [
        ("create", None),
        ("check", {"ticket": "fake-ticket", "device": "fake-session"}),
    ],
)
def test_qr_connection_reason_reaches_client(qr_client, monkeypatch, stage, body):
    def handler(request):
        raise CommunityConnectionError(
            "社区代理连接失败，请检查代理服务后重试", request=request
        )

    _install_upstream(monkeypatch, handler)
    response = qr_client.post(f"/api/login/skland/qr/{stage}", json=body)
    assert response.status_code == 400
    assert "检查代理服务" in response.json()["message"]


@pytest.mark.parametrize(
    ("status", "message", "expected"),
    [
        (100, "未扫码", "Init"),
        (101, "已扫码待确认", "Scanned"),
        (102, "二维码已失效", "Expired"),
        (103, "用户取消", "Canceled"),
        (500, "服务繁忙", "Error"),
    ],
)
def test_qr_status_is_not_confused_with_success(
    qr_client, monkeypatch, status, message, expected
):
    _install_upstream(
        monkeypatch,
        lambda _: httpx.Response(200, json={"status": status, "msg": message}),
    )
    response = qr_client.post(
        "/api/login/skland/qr/check",
        json={
            "ticket": "fake-ticket",
            "device": "fake-session",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == expected
    assert response.json()["scan_code"] == ""


def test_qr_confirm_exchange_and_save_complete_credential(qr_client, monkeypatch):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if str(request.url) == skland.SKLAND_SCAN_CREATE_URL:
            return httpx.Response(
                200,
                json={
                    "status": 0,
                    "data": {
                        "scanId": "fake-ticket",
                        "scanUrl": "https://example.invalid/scan",
                    },
                },
            )
        if request.url.path == "/general/v1/scan_status":
            assert request.url.params["scanId"] == "fake-ticket"
            return httpx.Response(
                200, json={"status": 0, "data": {"scanCode": "fake-scan-code"}}
            )
        if request.url.host == "fp-it.portal101.cn":
            return httpx.Response(
                200, json={"code": 1100, "detail": {"deviceId": "fake-device"}}
            )
        if str(request.url) == skland.SKLAND_SCAN_TOKEN_URL:
            assert json.loads(request.content) == {"scanCode": "fake-scan-code"}
            return httpx.Response(
                200, json={"status": 0, "data": {"token": "fake-oauth-token"}}
            )
        if str(request.url) == skland.SKLAND_GRANT_CODE_URL:
            assert json.loads(request.content)["token"] == "fake-oauth-token"
            return httpx.Response(
                200, json={"status": 0, "data": {"code": "fake-grant"}}
            )
        if str(request.url) == skland.SKLAND_CRED_CODE_URL:
            assert request.headers["did"] == "Bfake-device"
            assert json.loads(request.content) == {"code": "fake-grant", "kind": 1}
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "token": "fake-sign-token",
                        "cred": "fake-cred",
                        "userId": "fake-user",
                    },
                },
            )
        raise AssertionError("意外的上游请求")

    _install_upstream(monkeypatch, handler)
    uid = qr_client.post("/api/accounts").json()["data"]["uid"]
    created = qr_client.post("/api/login/skland/qr/create").json()
    assert paths == ["/general/v1/gen_scan/login"]
    checked = qr_client.post(
        "/api/login/skland/qr/check",
        json={
            "ticket": created["ticket"],
            "device": created["device"],
        },
    ).json()
    assert checked["status"] == "Confirmed"
    saved = qr_client.post(
        "/api/login/skland/qr/save",
        json={
            "account_uid": uid,
            "scan_code": checked["scan_code"],
        },
    )
    assert saved.status_code == 200
    assert json.loads(state.require_account(uid).SklandToken) == {
        "oauthToken": "fake-oauth-token",
        "token": "fake-sign-token",
        "cred": "fake-cred",
        "userId": "fake-user",
    }
    assert paths[-3:] == [
        "/user/auth/v1/token_by_scan_code",
        "/user/oauth2/v2/grant",
        "/web/v1/user/auth/generate_cred_by_code",
    ]


def test_failed_exchange_does_not_overwrite_saved_credential(qr_client, monkeypatch):
    def handler(request):
        if request.url.host == "fp-it.portal101.cn":
            return httpx.Response(
                200, json={"code": 1100, "detail": {"deviceId": "fake-device"}}
            )
        return httpx.Response(200, json={"status": 102, "msg": "扫码凭证已过期"})

    _install_upstream(monkeypatch, handler)
    uid = qr_client.post("/api/accounts").json()["data"]["uid"]
    qr_client.post(
        "/api/accounts/update",
        json={"accountId": uid, "data": {"SklandToken": "fake-old-token"}},
    )
    response = qr_client.post(
        "/api/login/skland/qr/save",
        json={
            "account_uid": uid,
            "scan_code": "fake-expired-code",
        },
    )
    assert response.status_code == 400
    assert "失效" in response.json()["message"]
    assert state.require_account(uid).SklandToken == "fake-old-token"
