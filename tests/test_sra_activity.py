"""SRA 客户端的解析、时间补全与失败降级测试；用固定样本与假传输层，不访问真实网络。"""

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from loguru import logger  # noqa: E402

from app.services.network import network  # noqa: E402
from app.tools import sra_activity  # noqa: E402

# 固定样本：字段与实测一致（kind 只有部分游戏有、cover 可能为 null、时间不带时区）。
SAMPLE = {
    "version": "3.4",
    "versionName": "3.4 测试版本",
    "cover": "https://example.invalid/version.png",
    "startTime": "2026-10-05T12:00:00",
    "endTime": "2026-11-15T03:59:59",
    "activities": [
        {
            "name": "限时活动",
            "kind": "限时活动",
            "description": "第一段描述",
            "startTime": "2026-10-05T12:00:00",
            "endTime": "2026-10-20T03:59:59",
            "cover": "https://example.invalid/a.png",
        },
        {
            # 实测 ww 没有 kind 字段、xtlr 全都没有封面：留空而不是当成错误。
            "name": "无分类无封面",
            "description": "",
            "startTime": "2026-09-01T04:00:00",
            "endTime": "2026-12-01T03:59:59",
            "cover": None,
        },
        {"name": "  ", "startTime": "2026-10-01T04:00:00"},  # 没有名字：过滤掉
        "不是对象",  # 结构不对：跳过
    ],
}


def _transport(payload: object, status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, text="上游错误正文")
        if isinstance(payload, httpx.Response):
            return payload
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


def _patch_network(monkeypatch, transport: httpx.MockTransport) -> None:
    """把社区请求工厂换成注入假传输层的等价客户端（与仓库其它测试一致）。"""
    monkeypatch.setattr(
        network, "client", lambda **options: httpx.AsyncClient(transport=transport)
    )


def test_beijing_time_completes_missing_offset():
    assert sra_activity.beijing_time("2026-10-05T12:00:00") == "2026-10-05T12:00:00+08:00"
    assert sra_activity.beijing_time("2026-10-05T12:00:00Z") == "2026-10-05T12:00:00Z"
    already = "2026-10-05T12:00:00+09:00"
    assert sra_activity.beijing_time(already) == already
    # 负偏移也算已带时区，不能再拼一个 +08:00。
    negative = "2026-10-05T12:00:00-05:00"
    assert sra_activity.beijing_time(negative) == negative
    # 只有日期时补零点：直接拼偏移会得到 "2026-10-05+08:00"，不是合法 ISO 串。
    assert sra_activity.beijing_time("2026-10-05") == "2026-10-05T00:00:00+08:00"
    assert sra_activity.beijing_time("  2026-10-05T12:00:00 ") == "2026-10-05T12:00:00+08:00"


def test_beijing_time_returns_empty_for_missing_values():
    for value in (None, "", "   ", 123, {"a": 1}, []):
        assert sra_activity.beijing_time(value) == ""


def test_normalize_maps_item_fields():
    data = sra_activity.normalize(SAMPLE)
    assert data is not None
    assert data["version"] == "3.4"
    assert data["versionName"] == "3.4 测试版本"
    assert data["cover"] == "https://example.invalid/version.png"
    assert data["startTime"] == "2026-10-05T12:00:00+08:00"
    names = [item["name"] for item in data["activities"]]
    assert names == ["限时活动", "无分类无封面"]  # 空名字与非法条目被过滤
    first, second = data["activities"]
    assert first["kind"] == "限时活动"
    assert first["cover"] == "https://example.invalid/a.png"
    assert second["kind"] == ""  # 上游没有该字段：留空，不报错
    assert second["cover"] == ""  # cover 为 null：换成空串，前端自备占位
    assert second["description"] == ""


def test_normalize_requires_activities_list():
    assert sra_activity.normalize(None) is None
    assert sra_activity.normalize("不是对象") is None
    assert sra_activity.normalize({}) is None
    assert sra_activity.normalize({"activities": {"a": 1}}) is None
    empty = sra_activity.normalize({"activities": []})
    assert empty is not None and empty["activities"] == []


def test_module_has_no_nonebot_dependency():
    source = Path(sra_activity.__file__).read_text(encoding="utf-8")
    assert "nonebot" not in source
    assert "starrailassistant.top" in source  # 来源写在代码注释里
    assert sra_activity.ACTIVITY_BASE.endswith("/api/v1/activity")


@pytest.mark.asyncio
async def test_fetch_activities_parses_payload(monkeypatch):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=SAMPLE)

    _patch_network(monkeypatch, httpx.MockTransport(handler))
    data = await sra_activity.fetch_activities("end")
    assert seen == ["https://starrailassistant.top/api/v1/activity/end.json"]
    assert data is not None and len(data["activities"]) == 2


@pytest.mark.asyncio
async def test_fetch_activities_always_carries_timezone(monkeypatch):
    """时间必须补上 +08:00，否则前端按本地时区解析会整体偏移。"""
    _patch_network(monkeypatch, _transport(SAMPLE))
    data = await sra_activity.fetch_activities("ak")
    assert data is not None
    for item in data["activities"]:
        assert item["startTime"].endswith("+08:00")
        assert item["endTime"].endswith("+08:00")


@pytest.mark.asyncio
async def test_fetch_activities_degrades_silently(monkeypatch):
    _patch_network(monkeypatch, _transport(None, status=500))
    assert await sra_activity.fetch_activities("ys") is None
    _patch_network(
        monkeypatch, httpx.MockTransport(lambda request: httpx.Response(200, text="不是 JSON"))
    )
    assert await sra_activity.fetch_activities("ys") is None
    _patch_network(monkeypatch, _transport({"foo": "bar"}))
    assert await sra_activity.fetch_activities("ys") is None


@pytest.mark.asyncio
async def test_fetch_activities_reports_connection_failure(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("连接失败", request=request)

    _patch_network(monkeypatch, httpx.MockTransport(handler))
    assert await sra_activity.fetch_activities("zzz") is None


@pytest.mark.asyncio
async def test_fetch_activities_failure_returns_none_without_body(monkeypatch, capsys):
    """失败只留类型，不把上游响应体写进日志或返回值。"""
    _patch_network(monkeypatch, _transport(None, status=502))
    assert await sra_activity.fetch_activities("nte") is None
    assert "上游错误正文" not in capsys.readouterr().err

@pytest.mark.asyncio
async def test_fetch_retries_transient_error_then_succeeds(monkeypatch):
    """弱网抖动（5xx/超时）重试一次就能拿到数据，不该让日历直接降级。"""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(503, text="上游暂时不可用")
        return httpx.Response(200, json=SAMPLE)

    _patch_network(monkeypatch, httpx.MockTransport(handler))
    data = await sra_activity.fetch_activities("end")
    assert len(calls) == 2  # 失败一次、重试成功
    assert data is not None and len(data["activities"]) == 2


@pytest.mark.asyncio
async def test_fetch_does_not_retry_non_retryable_status(monkeypatch):
    """404 这类确定性错误重试也没用，只发一次请求。"""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(404)

    _patch_network(monkeypatch, httpx.MockTransport(handler))
    assert await sra_activity.fetch_activities("ys") is None
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_fetch_enters_cooldown_after_failure(monkeypatch):
    """失败后 60 秒内不再回源：否则每次进日历页都要重试一轮。"""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(500)

    _patch_network(monkeypatch, httpx.MockTransport(handler))
    assert await sra_activity.fetch_activities("zzz") is None
    attempts = len(seen)
    assert attempts == sra_activity.MAX_ATTEMPTS

    # 冷却期内即使上游已经好了，也不会再发请求。
    _patch_network(monkeypatch, _transport(SAMPLE))
    assert await sra_activity.fetch_activities("zzz") is None
    assert len(seen) == attempts

    # 手动复位后才重新回源。
    sra_activity.reset_failure_state()
    data = await sra_activity.fetch_activities("zzz")
    assert data is not None


@pytest.mark.asyncio
async def test_fetch_success_clears_cooldown(monkeypatch):
    """成功后清掉冷却记录，下一次失败要从头计冷却而不是沿用旧时间。"""
    _patch_network(monkeypatch, _transport(None, status=500))
    assert await sra_activity.fetch_activities("nte") is None
    sra_activity.reset_failure_state()
    _patch_network(monkeypatch, _transport(SAMPLE))
    assert await sra_activity.fetch_activities("nte") is not None
    assert "nte" not in sra_activity._cooldown_until
    assert "nte" not in sra_activity._warned_at


@pytest.mark.asyncio
async def test_fetch_warns_at_most_once_per_hour(monkeypatch):
    """弱网失败按小时节流：日历页反复刷新不该把日志刷满。"""
    messages: list[str] = []
    # loguru 的 sink 在导入时绑定原始 stderr，pytest 的 capsys/capfd 都抓不到，另挂一个 sink。
    handler_id = logger.add(lambda message: messages.append(message), level="WARNING")
    try:
        _patch_network(monkeypatch, _transport(None, status=503))
        assert await sra_activity.fetch_activities("ww") is None
        assert any("取 SRA 活动数据失败" in message for message in messages)

        # 只清冷却、保留告警时刻，模拟 60 秒后再次失败。
        messages.clear()
        sra_activity._cooldown_until.pop("ww", None)
        assert await sra_activity.fetch_activities("ww") is None
        assert messages == []
    finally:
        logger.remove(handler_id)
