"""明日方舟日历的解析、缓存与降级测试；用假传输层，不访问真实网络。"""

import sys
import time
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.network import network  # noqa: E402
from app.tools import game_calendar_arknights as calendar  # noqa: E402
from app.tools.akedata_client import AkedataError  # noqa: E402

NOW = 1767196800.0  # 2026-01-01 00:00:00+08:00（unix 秒，与本地时区无关）
DAY = 86400.0


def _base_now(now: float | None) -> float:
    """刷新流程用真实当前时间，纯函数测试用固定时间。"""
    return time.time() if now is None else now


def _activity_table(now: float = NOW) -> dict:
    NOW = now
    return {
        "basicInfo": {
            "act1": {
                "id": "act1",
                "name": "测试主线活动",
                "type": "TYPE_ACT",
                "startTime": int(NOW - 2 * DAY),
                "endTime": int(NOW + 5 * DAY),
                "isReplicate": False,
            },
            "act2": {
                "id": "act2",
                "name": "测试复刻活动",
                "type": "TYPE_ACT",
                "startTime": int(NOW - 400 * DAY),
                "endTime": int(NOW - 390 * DAY),
                "isReplicate": True,
            },
            "act3": {
                "id": "act3",
                "name": "测试签到",
                "type": "CHECKIN",
                "startTime": int(NOW - DAY),
                "endTime": int(NOW + DAY),
                "isReplicate": False,
            },
            "act4": {"id": "act4", "name": "", "type": "TYPE_ACT", "startTime": 1, "endTime": 2},
        }
    }


def _gacha_table(now: float = NOW) -> dict:
    NOW = now
    return {
        "gachaPoolClient": [
            {
                "gachaPoolId": "LIMITED_TRAP_1",
                "gachaPoolName": "限定寻访·测试",
                "openTime": int(NOW - DAY),
                "endTime": int(NOW + 10 * DAY),
            },
            {
                "gachaPoolId": "NORM_TRAP_2",
                "gachaPoolName": "适合多种场合的强力干员",
                "openTime": int(NOW - DAY),
                "endTime": int(NOW + 10 * DAY),
            },
            {
                "gachaPoolId": "NEWBIE_1",  # 前缀不匹配，跳过
                "gachaPoolName": "新手池",
                "openTime": int(NOW - DAY),
                "endTime": int(NOW + 10 * DAY),
            },
            {
                "gachaPoolId": "CLASSIC_1",  # 覆盖所有版本（超过 PERMANENT）
                "gachaPoolName": "常驻中坚",
                "openTime": 1,
                "endTime": int(NOW + 400 * DAY),
            },
        ]
    }


def test_build_filters_and_classifies():
    activities, pools = calendar.build(_activity_table(), _gacha_table(), None, {}, NOW)
    names = [row["name"] for row in activities]
    assert names == ["测试主线活动", "测试签到"]  # 空名字与久远的活动被过滤
    kinds = {row["id"]: row["kind"] for row in activities}
    assert kinds == {"act1": "活动", "act3": "签到"}
    pool_ids = [row["id"] for row in pools]
    assert pool_ids == ["LIMITED_TRAP_1", "NORM_TRAP_2"]  # 新手前缀与超长池被跳过
    standard = next(row for row in pools if row["id"] == "NORM_TRAP_2")
    assert standard["name"] == "标准寻访"  # 通用名字换成池子分类
    assert standard["up"] == []


def test_build_marks_replicate_activities():
    table = _activity_table()
    table["basicInfo"]["act5"] = {
        "id": "act5",
        "name": "测试复刻",
        "type": "TYPE_ACT",
        "startTime": int(NOW - DAY),
        "endTime": int(NOW + DAY),
        "isReplicate": True,
    }
    activities, _ = calendar.build(table, _gacha_table(), None, {}, NOW)
    assert next(row for row in activities if row["id"] == "act5")["kind"] == "活动·复刻"


def test_build_reads_up_operators_from_pool_details():
    details = {
        "gachaPoolClient": [
            {
                "gachaPoolId": "LIMITED_TRAP_1",
                "gachaPoolDetail": {
                    "detailInfo": {
                        "upCharInfo": {
                            "perCharList": [
                                {"rarityRank": 5, "charIdList": ["char_1"]},
                                {"rarityRank": 4, "charIdList": ["char_2"]},
                            ]
                        }
                    }
                },
            }
        ]
    }
    _, pools = calendar.build(
        _activity_table(), _gacha_table(), details, {"char_1": "干员X", "char_2": "干员Y"}, NOW
    )
    assert pools[0]["up"] == ["干员X"]


def test_version_due_rules():
    assert calendar.version_due({}, "v1", NOW) is True
    fresh = {"version": "v1", calendar.GAME_ACTIVITIES_KEY: [], "pools": [], "fetched": NOW}
    assert calendar.version_due(fresh, "v1", NOW) is False
    assert calendar.version_due(fresh, "v2", NOW) is True
    assert calendar.version_due(fresh, "v1", NOW + calendar.MAX_AGE + 1) is True
    del fresh["pools"]
    assert calendar.version_due(fresh, "v1", NOW) is True


def test_load_and_write_cache(tmp_path):
    path = tmp_path / "wiki" / "arknights.json"
    assert calendar.load(path) == {}
    path.parent.mkdir(parents=True)
    path.write_text("不是 JSON", encoding="utf-8")
    assert calendar.load(path) == {}
    calendar.write_cache(path, {"version": "v1"})
    assert calendar.load(path) == {"version": "v1"}
    assert list(path.parent.iterdir()) == [path]  # 没有留下临时文件


def test_to_calendar_rows_maps_contract_fields():
    index = {
        "activities": [
            {"id": "act1", "name": "活动一", "kind": "活动", "start": int(NOW - DAY), "end": int(NOW + DAY), "image": "https://example.invalid/a.png"}
        ],
        "pools": [
            {"id": "P1", "name": "寻访一", "kind": "限定寻访", "up": ["干员X", "干员Y"], "start": int(NOW + DAY), "end": int(NOW + 2 * DAY)}
        ],
        "pool_images": {"P1": "https://example.invalid/p.png"},
    }
    rows = calendar.to_calendar_rows(index, now=NOW)
    assert [row["kind"] for row in rows] == ["activity", "gacha"]
    activity, pool = rows
    assert activity["status"] == "进行中"
    assert activity["startsAt"].endswith("+08:00")
    assert activity["banner"] == "https://example.invalid/a.png"
    assert pool["status"] == "即将开始"
    assert pool["subtitle"] == "UP：干员X、干员Y"
    assert pool["banner"] == "https://example.invalid/p.png"


def test_epoch_and_moment_handle_bad_values():
    assert calendar._epoch(0) is None
    assert calendar._epoch(None) is None
    assert calendar._epoch("x") is None
    assert calendar._epoch("1767196800") == 1767196800
    assert calendar._moment(0) == ""
    # 该 epoch 对应北京时间 2026-01-01 00:00:00。必须按 UTC+8 换算，
    # 不能依赖主机时区：在 UTC+8 主机上叠加 +8 小时会算成 08:00:00。
    assert calendar._moment(NOW) == "2026-01-01T00:00:00+08:00"
    assert calendar._moment(NOW + 8 * 3600) == "2026-01-01T08:00:00+08:00"


def _transport(version: str, activity: dict, gacha: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == calendar.VERSION_URL:
            return httpx.Response(200, text=version + "\n")
        if url == calendar.ACTIVITY_URL:
            return httpx.Response(200, json=activity)
        if url == calendar.GACHA_URL:
            return httpx.Response(200, json=gacha)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_refresh_downloads_and_caches(tmp_path, monkeypatch):
    path = tmp_path / "arknights.json"
    # refresh 用的是真实当前时间，因此这里的数据也以当前时间为基准。
    now = _base_now(None)
    transport = _transport("v-test", _activity_table(now), _gacha_table(now))
    monkeypatch.setattr(
        network, "client", lambda **options: httpx.AsyncClient(transport=transport, trust_env=False)
    )
    outcome = await calendar.refresh(path)
    assert outcome.startswith("已同步 v-test")
    cached = calendar.load(path)
    assert cached["version"] == "v-test"
    assert len(cached[calendar.GAME_ACTIVITIES_KEY]) == 2
    assert len(cached["pools"]) == 2
    # 没有 PRTS 时合并结果等于游戏表；pool_images 由未接入的 PRTS 分支填充，保持为空。
    assert cached["activities"] == cached[calendar.GAME_ACTIVITIES_KEY]
    assert cached["pool_images"] == {}


@pytest.mark.asyncio
async def test_refresh_skips_when_version_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "arknights.json"
    calendar.write_cache(
        path,
        {
            "version": "v-test",
            "fetched": time.time(),
            calendar.GAME_ACTIVITIES_KEY: [],
            "pools": [],
        },
    )
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text="v-test")

    monkeypatch.setattr(
        network,
        "client",
        lambda **options: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), trust_env=False
        ),
    )
    assert await calendar.refresh(path) == "已是最新"
    assert calls == [calendar.VERSION_URL]


@pytest.mark.asyncio
async def test_refresh_reports_errors_without_response_body(tmp_path, monkeypatch):
    path = tmp_path / "arknights.json"

    def handler(request: httpx.Request) -> httpx.Response:
        # 版本文件正常，活动表出错：错误里只保留端点与类型，不回显响应体。
        if str(request.url) == calendar.VERSION_URL:
            return httpx.Response(200, text="v-test")
        return httpx.Response(500, text="上游错误正文")

    monkeypatch.setattr(
        network,
        "client",
        lambda **options: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), trust_env=False
        ),
    )
    with pytest.raises(AkedataError) as caught:
        await calendar.refresh(path)
    assert "上游错误正文" not in str(caught.value)
    assert "activity_table.json" in str(caught.value)
    assert "HTTPStatusError" in str(caught.value)
    assert not path.exists()


@pytest.mark.asyncio
async def test_refresh_reports_version_file_failure(tmp_path, monkeypatch):
    path = tmp_path / "arknights.json"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="上游错误正文")

    monkeypatch.setattr(
        network,
        "client",
        lambda **options: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), trust_env=False
        ),
    )
    with pytest.raises(AkedataError) as caught:
        await calendar.refresh(path)
    assert "版本文件请求失败" in str(caught.value)
    assert "上游错误正文" not in str(caught.value)


def test_prts_is_not_wired_up_yet():
    """时间不足时的降级：只接入游戏表单一来源，PRTS 尚未接入。"""
    assert calendar.PRTS_ENABLED is False
    source = Path(calendar.__file__).read_text(encoding="utf-8")
    assert "prts.wiki" in source  # 来源与许可写在代码注释里
    assert "CC BY-NC-SA" in source
    assert "AGPL" in source
    for name in ("parse_wiki", "merge", "pool_images"):
        assert not hasattr(calendar, name)
