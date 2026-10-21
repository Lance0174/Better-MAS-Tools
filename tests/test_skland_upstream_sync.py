"""森空岛链路的本地回归：服务器取时、设备验证重试与失败原因透传。

对应 AUTO-MAS 8333f11a / b834a123 / 29a98a88 / 5b5ebbd5 的同步，不访问真实网络。
"""

import time

import httpx
import pytest

from app.tools import skland
from app.tools.game_sign_result import build_skland_sign_results


@pytest.fixture(autouse=True)
def _reset_server_clock():
    """每个用例都从"未取到服务器时间"开始，避免用例间互相影响。"""

    skland._server_clock = None
    yield
    skland._server_clock = None


def _response(
    status_code: int = 200,
    *,
    payload: object | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request("GET", "https://zonai.skland.com/web/v1/user/auth/generate_cred_by_code")
    if payload is None:
        return httpx.Response(status_code, headers=headers or {}, request=request)
    return httpx.Response(status_code, json=payload, headers=headers or {}, request=request)


def test_response_server_time_prefers_payload_timestamp():
    response = _response(payload={"timestamp": 1_700_000_000}, headers={"Date": "Mon, 01 Jan 2024 00:00:00 GMT"})
    assert skland._response_server_time(response, {"timestamp": 1_700_000_000}) == 1_700_000_000


def test_response_server_time_falls_back_to_date_header():
    response = _response(headers={"Date": "Mon, 01 Jan 2024 00:00:00 GMT"})
    value = skland._response_server_time(response)
    assert value is not None
    assert abs(value - 1_704_067_200) < 1


def test_response_server_time_ignores_cached_and_millisecond_values():
    cached = _response(payload={"timestamp": 1_700_000_000}, headers={"Age": "120"})
    assert skland._response_server_time(cached, {"timestamp": 1_700_000_000}) is None

    milliseconds = _response(payload={"timestamp": 1_700_000_000_000})
    assert skland._response_server_time(milliseconds, {"timestamp": 1_700_000_000_000}) is None


def test_server_clock_drives_signed_timestamp(monkeypatch):
    monkeypatch.setattr(skland, "_server_clock", (1_700_000_000.0, time.monotonic()))
    headers = skland.build_skland_signed_headers(
        "token",
        path="/api/v1/game/attendance",
        body_or_query="",
        device_id="Bdevice",
        headers={},
    )
    # 与 _server_clock 相差不足 1 秒（仅扣除签名用的 2 秒余量）。
    assert abs(int(headers["timestamp"]) - 1_699_999_998) <= 1


def test_system_time_offset_reports_none_without_sample():
    assert skland.current_system_time_offset() is None


def test_system_time_offset_reflects_sample(monkeypatch):
    monkeypatch.setattr(skland, "_server_clock", (time.time() + 120, time.monotonic()))
    offset = skland.current_system_time_offset()
    assert offset is not None and 115 < offset < 125


def test_parse_json_object_keeps_already_signed_payload():
    response = _response(
        403,
        payload={"code": 10001, "message": "请勿重复签到"},
    )
    # 已签到必须以业务码为准，不能被 HTTP 403 覆盖。
    payload = skland._parse_json_object(response, allow_already_signed=True)
    assert payload["code"] == 10001


def test_parse_json_object_rejects_other_http_errors_when_allowing_signed():
    response = _response(403, payload={"code": 10002, "message": "风控拦截"})
    with pytest.raises(ValueError, match="HTTP 403"):
        skland._parse_json_object(response, allow_already_signed=True)


def test_parse_json_object_reports_decode_failure_with_hint():
    response = _response(200)
    response._content = b"<html>proxy error</html>"  # noqa: SLF001 - 构造非 JSON 响应
    with pytest.raises(ValueError, match="解码失败"):
        skland._parse_json_object(response, allow_already_signed=True)


@pytest.mark.asyncio
async def test_get_device_id_retries_transient_rejection(monkeypatch):
    calls = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(200, json={"code": 1901}, request=request)
        return httpx.Response(200, json={"code": 1100, "detail": {"deviceId": "abc"}}, request=request)

    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(skland.asyncio, "sleep", no_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await skland.get_device_id(client=client) == "Babc"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_get_device_id_reports_code_without_leaking_response(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 1901, "secret": "raw-body"}, request=request)

    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(skland.asyncio, "sleep", no_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError) as error:
            await skland.get_device_id(client=client)
    assert "1901" in str(error.value)
    assert "raw-body" not in str(error.value)


def test_sign_results_use_reported_failure_reason():
    results = build_skland_sign_results(
        {
            "arknights": {
                "成功": [],
                "重复": [],
                "失败": ["角色A/角色A(1)"],
                "总计": 1,
                "奖励": {},
                "失败原因": {"角色A/角色A(1)": "森空岛凭据已失效"},
            }
        },
        account_name="别名",
        account_uid="uid-1",
    )
    failed = [item for item in results if item["status"] == "失败"]
    assert failed and failed[0]["reason"] == "森空岛凭据已失效"


def test_sign_results_fall_back_to_generic_reason():
    results = build_skland_sign_results(
        {
            "arknights": {
                "成功": [],
                "重复": [],
                "失败": ["角色A/角色A(1)"],
                "总计": 1,
                "奖励": {},
            }
        },
        account_name="别名",
        account_uid="uid-1",
    )
    failed = [item for item in results if item["status"] == "失败"]
    assert failed and failed[0]["reason"] == "签到失败"
