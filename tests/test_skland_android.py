"""森空岛手机链路：真实编排与网络桥、合成原生响应，不访问真实账号。"""

import asyncio
import base64
import gzip
import json
from email.utils import formatdate

import httpx
import pytest

from app.core.android_runtime import AndroidRuntime
from app.core.community_activity import reset_activity_cache
from app.core.state import state
from app.models.config import SavedState
from app.services.network import network
from app.tools import skland


class SklandNativeFixture:
    def __init__(self):
        self.saved = SavedState().model_dump_json()
        self.requests: list[httpx.Request] = []
        self.device_error = False
        self.storage_error = False
        self.gzip_responses = False

    async def __call__(self, operation: str, serialized: str) -> str:
        payload = json.loads(serialized)
        if operation == "state.read":
            return json.dumps({"state": self.saved})
        if operation == "state.write":
            if self.storage_error:
                return '{"saved":false}'
            self.saved = payload["state"]
            return '{"saved":true}'
        if operation == "wiki.read":
            return '{"content":null}'
        assert operation == "http.request"
        request = httpx.Request(
            payload["method"],
            payload["url"],
            headers=payload["headers"],
            content=base64.b64decode(payload["body"], validate=True),
        )
        self.requests.append(request)
        if self.device_error and request.url.host == "fp-it.portal101.cn":
            return '{"error":"network"}'
        response = httpx.Response(
            200, json=self.upstream(request), headers={"date": formatdate(usegmt=True)}
        )
        body = response.content
        headers = list(response.headers.multi_items())
        if self.gzip_responses:
            assert "gzip" in request.headers["accept-encoding"]
            body = gzip.compress(body)
            headers = [
                (name, value) for name, value in headers if name != "content-length"
            ]
            headers.extend(
                [("content-encoding", "gzip"), ("content-length", str(len(body)))]
            )
        return json.dumps(
            {
                "status": response.status_code,
                "headers": headers,
                "body": base64.b64encode(body).decode("ascii"),
            }
        )

    def upstream(self, request: httpx.Request) -> dict:
        url = str(request.url)
        if url == skland.SKLAND_SCAN_CREATE_URL:
            return {
                "status": 0,
                "data": {
                    "scanId": "fixture-ticket",
                    "scanUrl": "https://example.invalid/fixture-scan",
                },
            }
        if request.url.path == "/general/v1/scan_status":
            assert request.url.params["scanId"] == "fixture-ticket"
            return {"status": 0, "data": {"scanCode": "fixture-scan-code"}}
        if request.url.host == "fp-it.portal101.cn":
            assert request.url.path == "/deviceprofile/v4"
            return {"code": 1100, "detail": {"deviceId": "fixture-device"}}
        if url == skland.SKLAND_SCAN_TOKEN_URL:
            assert json.loads(request.content) == {"scanCode": "fixture-scan-code"}
            return {"status": 0, "data": {"token": "fixture-oauth"}}
        if url == skland.SKLAND_GRANT_CODE_URL:
            assert json.loads(request.content)["token"] == "fixture-oauth"
            return {
                "status": 0,
                "data": {"code": "fixture-grant", "token": "fixture-game-grant"},
            }
        if request.url.path == "/account/binding/v1/u8_token_by_uid":
            assert json.loads(request.content) == {
                "uid": "12345678",
                "token": "fixture-game-grant",
            }
            return {"status": 0, "data": {"token": "fixture-role-token"}}
        if request.url.host == "ak.hypergryph.com":
            if request.url.path == "/user/api/role/login":
                assert json.loads(request.content) == {"token": "fixture-role-token"}
                return {"code": 0}
            assert request.headers["x-account-token"] == "fixture-oauth"
            assert request.headers["x-role-token"] == "fixture-role-token"
            if request.url.path.endswith("/gacha/cate"):
                return {"code": 0, "data": [{"id": "normal"}]}
            assert request.url.path.endswith("/gacha/history")
            return {
                "code": 0,
                "data": {
                    "list": [
                        {
                            "gachaTs": 1794614400,
                            "pos": 1,
                            "charName": "合成寻访干员",
                            "charId": "fixture-char",
                            "rarity": 5,
                        }
                    ],
                    "hasMore": False,
                },
            }
        if url == skland.SKLAND_CRED_CODE_URL:
            assert request.headers["did"] == "Bfixture-device"
            assert json.loads(request.content) == {"code": "fixture-grant", "kind": 1}
            return {
                "code": 0,
                "data": {"cred": "fixture-cred", "token": "fixture-sign-token"},
            }
        assert request.headers["did"] == "Bfixture-device"
        assert request.headers["cred"] == "fixture-cred"
        assert request.headers["sign"]
        if url == skland.SKLAND_REFRESH_URL:
            return {"code": 0, "data": {"token": "fixture-refreshed-sign-token"}}
        if url == skland.SKLAND_BINDING_URL:
            return {
                "code": 0,
                "data": {
                    "list": [
                        {
                            "appCode": "arknights",
                            "bindingList": [
                                {"uid": "12345678", "nickName": "fixture-doctor"}
                            ],
                        },
                        {
                            "appCode": "endfield",
                            "bindingList": [
                                {
                                    "roles": [
                                        {
                                            "roleId": "87654321",
                                            "serverId": "1",
                                            "nickname": "fixture-admin",
                                        }
                                    ],
                                }
                            ],
                        },
                    ]
                },
            }
        if request.url.path == "/api/v1/game/player/info":
            assert request.url.params["uid"] == "12345678"
            return {"code": 0, "data": {"status": {"ap": {"current": 80, "max": 135}}}}
        if request.url.path == "/web/v1/game/endfield/card/detail":
            assert request.url.params["roleId"] == "87654321"
            assert request.headers["sk-game-role"] == "3_87654321_1"
            return {
                "code": 0,
                "data": {
                    "detail": {
                        "dailyMission": {
                            "dailyActivation": 20,
                            "maxDailyActivation": 100,
                        },
                    }
                },
            }
        if url == skland.SKLAND_ENDFIELD_SIGN_URL:
            assert request.method == "POST"
            assert request.content == b""
            assert request.headers["sk-game-role"] == "3_87654321_1"
            return {"code": 0, "data": {"awards": []}}
        if request.url.path == "/api/v1/game/attendance":
            if request.method == "GET":
                return {"code": 0, "data": {"records": []}}
            assert json.loads(request.content)["uid"] == "12345678"
            return {"code": 0, "data": {"awards": []}}
        raise AssertionError(f"意外的森空岛请求：{request.method} {request.url.path}")


@pytest.fixture
def native_skland(monkeypatch):
    monkeypatch.setattr(state, "data", SavedState())
    monkeypatch.setattr(state, "storage", None)
    monkeypatch.setattr(state, "revision", 0)
    monkeypatch.setattr(state, "lock", asyncio.Lock())
    for name in ("transport_factory", "proxy"):
        monkeypatch.setattr(network, name, None)
    monkeypatch.setattr(network, "local_connections", False)
    for name in ("_cached_device_id", "_cache_time", "_server_clock"):
        monkeypatch.setattr(skland, name, None)
    # external_state 应用会注册诊断 sink；测试结束后释放本用例创建的 sink。
    from app.main import logger

    sinks = []
    add_sink = logger.add

    def track_sink(*args, **kwargs):
        sink = add_sink(*args, **kwargs)
        sinks.append(sink)
        return sink

    monkeypatch.setattr(logger, "add", track_sink)
    reset_activity_cache()
    yield SklandNativeFixture()
    reset_activity_cache()
    for sink in sinks:
        logger.remove(sink)


async def _initialize(runtime: AndroidRuntime) -> httpx.AsyncClient:
    await runtime.initialize(run_startup=False)
    assert runtime.client is not None
    client = runtime.client
    session = (await client.get("/api/session")).json()
    client.headers["x-community-session"] = session["key"]
    return client


@pytest.mark.parametrize("compressed", [False, True], ids=["plain", "gzip"])
@pytest.mark.asyncio
async def test_android_qr_save_restart_notes_and_sign(native_skland, compressed):
    native_skland.gzip_responses = compressed
    runtime = AndroidRuntime(native_skland)
    client = await _initialize(runtime)
    try:
        uid = (await client.post("/api/accounts")).json()["data"]["uid"]
        created = (await client.post("/api/login/skland/qr/create")).json()
        checked = await client.post(
            "/api/login/skland/qr/check",
            json={"ticket": created["ticket"], "device": created["device"]},
        )
        assert checked.json()["status"] == "Confirmed"
        saved = await client.post(
            "/api/login/skland/qr/save",
            json={"account_uid": uid, "scan_code": checked.json()["scan_code"]},
        )
        assert saved.status_code == 200
        credential = json.loads(
            SavedState.model_validate_json(native_skland.saved)
            .accounts[uid]
            .SklandToken
        )
        assert credential["oauthToken"] == "fixture-oauth"
        assert credential["cred"] == "fixture-cred"
        assert credential["token"] == "fixture-sign-token"

        await client.aclose()
        # 重启后重新读取手机存储，强制设备验证也重新执行。
        state.data = SavedState()
        skland._cached_device_id = None
        skland._cache_time = None
        client = await _initialize(runtime)
        assert state.require_account(uid).SklandToken
        notes = await client.post("/api/activity", json={"refresh": True})
        assert notes.status_code == 200
        arknights = next(
            item for item in notes.json()["data"] if item["game"] == "明日方舟"
        )
        assert arknights["status"] == "success"
        assert arknights["roleUid"] == "12345678"
        assert arknights["resources"][0]["current"] == 80
        endfield = next(
            item for item in notes.json()["data"] if item["game"] == "终末地"
        )
        assert endfield["status"] == "success"
        assert endfield["roleUid"] == "87654321"
        assert endfield["tasks"][0]["completed"] == 20
        persisted = json.loads(
            SavedState.model_validate_json(native_skland.saved)
            .accounts[uid]
            .SklandToken
        )
        # 便笺查询只在本次会话刷新签名 Token，磁盘上的长期凭据仍完整。
        assert persisted["oauthToken"] == "fixture-oauth"
        assert persisted["cred"] == "fixture-cred"
        assert any(
            str(request.url) == skland.SKLAND_REFRESH_URL
            for request in native_skland.requests
        )

        fetched = await client.post(
            "/api/gacha/fetch",
            json={"game": "arknights", "accountId": uid, "playerUid": "12345678"},
        )
        assert fetched.status_code == 200
        assert fetched.json()["fetched"] == 1
        records = (await client.get("/api/gacha", params={"game": "arknights"})).json()
        assert records["data"][0]["name"] == "合成寻访干员"
        assert records["data"][0]["rarity"] == 6
        assert len(SavedState.model_validate_json(native_skland.saved).gacha) == 1
        requests_before = len(native_skland.requests)
        rejected = await client.post(
            "/api/gacha/fetch",
            json={"game": "endfield", "accountId": uid, "playerUid": "87654321"},
        )
        assert rejected.status_code == 400
        assert "仅明日方舟开放" in rejected.json()["message"]
        assert len(native_skland.requests) == requests_before

        signed = await client.post("/api/sign")
        assert signed.status_code == 200
        results = (await client.get("/api/status")).json()["results"]["森空岛"]
        game = next(item for item in results[0]["games"] if item["game"] == "明日方舟")
        assert game["status"] == "成功"
        endfield_sign = next(
            item for item in results[0]["games"] if item["game"] == "终末地"
        )
        assert endfield_sign["status"] == "成功"
        stored = SavedState.model_validate_json(native_skland.saved)
        assert stored.results
        assert stored.accounts[uid].LastSignDate
        assert (
            sum(
                request.url.host == "fp-it.portal101.cn"
                for request in native_skland.requests
            )
            == 2
        )
    finally:
        await client.aclose()


@pytest.mark.parametrize("stage", ["device", "storage"])
@pytest.mark.asyncio
async def test_android_failed_qr_save_keeps_previous_credential(native_skland, stage):
    runtime = AndroidRuntime(native_skland)
    client = await _initialize(runtime)
    try:
        uid = (await client.post("/api/accounts")).json()["data"]["uid"]
        old_credential = json.dumps({"oauthToken": "fixture-old-oauth"})
        changed = await client.post(
            "/api/accounts/update",
            json={"accountId": uid, "data": {"SklandToken": old_credential}},
        )
        assert changed.status_code == 200
        original_state = native_skland.saved
        native_skland.device_error = stage == "device"
        native_skland.storage_error = stage == "storage"
        response = await client.post(
            "/api/login/skland/qr/save",
            json={"account_uid": uid, "scan_code": "fixture-scan-code"},
        )
        assert response.status_code == 400
        assert state.require_account(uid).SklandToken == old_credential
        assert native_skland.saved == original_state
        assert "fixture-" not in response.json()["message"]
        if stage == "device":
            assert all(
                request.url.host == "fp-it.portal101.cn"
                for request in native_skland.requests
            )
    finally:
        await client.aclose()
