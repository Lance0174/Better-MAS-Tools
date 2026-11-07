"""多游戏活动日历的缓存、降级与隔离测试；用固定样本与假传输层，不访问真实网络。"""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import endfield_fixtures as fixtures  # noqa: E402

from app.services import endfield_wiki, game_calendar  # noqa: E402
from app.services.network import network  # noqa: E402
from app.tools import game_calendar_arknights  # noqa: E402

UTC8 = endfield_wiki.UTC8
NOW = datetime.now(tz=UTC8)


def _stamp(delta: timedelta) -> str:
    return (NOW + delta).strftime("%Y-%m-%dT%H:%M:%S")


# 固定样本：字段与实测一致，时间不带时区，kind 只有部分游戏有，cover 可能缺失。
def _sample(*, upcoming: bool = False, missing_cover: bool = False) -> dict:
    start = _stamp(timedelta(days=3 if upcoming else -1))
    return {
        "version": "test-1",
        "versionName": "测试版本",
        "cover": "https://example.invalid/version.png",
        "startTime": _stamp(timedelta(days=-1)),
        "endTime": _stamp(timedelta(days=20)),
        "activities": [
            {
                "name": "测试活动一",
                "kind": "限时活动",
                "description": "第一段描述",
                "startTime": start,
                "endTime": _stamp(timedelta(days=10)),
                "cover": "" if missing_cover else "https://example.invalid/a.png",
            },
            {
                "name": "测试活动二",
                "kind": "",
                "description": "",
                "startTime": _stamp(timedelta(days=-2)),
                "endTime": _stamp(timedelta(days=-1)),
                "cover": "",
            },
        ],
    }


def _index_around_now() -> dict:
    """把固定索引里的活动与卡池时间挪到当前时间附近，便于验证日历过滤与状态。"""
    stamp = (NOW - timedelta(days=1)).strftime("%Y/%m/%d %H:%M:%S")
    close = (NOW + timedelta(days=10)).strftime("%Y/%m/%d %H:%M:%S")
    index = fixtures.minimal_index()
    for row in (*index["calendar"]["activities"], *index["calendar"]["pools"]):
        row["open"], row["close"] = stamp, close
    return index


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _patch_network(monkeypatch, routes: dict[str, object], seen: list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(str(request.url))
        payload = routes.get(str(request.url))
        if payload is None:
            return httpx.Response(500, text="上游错误正文")
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(
        network,
        "client",
        lambda **options: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.fixture(autouse=True)
def _clean_memory():
    """进程内缓存按数据目录隔离，测试之间仍显式复位，避免互相影响。"""
    game_calendar.clear_memory()
    yield
    game_calendar.clear_memory()


def _store(tmp_path: Path) -> endfield_wiki.WikiStore:
    return endfield_wiki.WikiStore(tmp_path / "data")


def test_game_enumeration_matches_sra_sources():
    assert game_calendar.CALENDAR_GAMES == (
        "endfield",
        "arknights",
        "genshin",
        "starrail",
        "zenless",
        "wutheringwaves",
        "nte",
        "stellasora",
        "infinitynikki",
    )
    assert game_calendar.SRA_SOURCES == {
        "endfield": "end",
        "arknights": "ak",
        "genshin": "ys",
        "starrail": "sr",
        "zenless": "zzz",
        "wutheringwaves": "ww",
        "nte": "nte",
        "stellasora": "xtlr",
        "infinitynikki": "infinitynikki",
    }
    assert set(game_calendar.GAME_NAMES) == set(game_calendar.CALENDAR_GAMES)
    assert endfield_wiki.CALENDAR_GAMES == game_calendar.CALENDAR_GAMES


def test_rows_map_contract_fields_and_status(tmp_path):
    store = _store(tmp_path)
    directory = store.wiki_directory
    rows = game_calendar.to_calendar_rows("starrail", _sample(), now=NOW.timestamp())
    # 按开始时间升序：开始得更早的"测试活动二"在前。
    assert [row["title"] for row in rows] == ["测试活动二", "测试活动一"]
    by_title = {row["title"]: row for row in rows}
    current, ended = by_title["测试活动一"], by_title["测试活动二"]
    assert current["game"] == "starrail"
    assert current["kind"] == "activity"
    assert current["subtitle"] == "第一段描述"
    assert current["startsAt"].endswith("+08:00") and current["endsAt"].endswith("+08:00")
    assert current["status"] == "进行中"
    assert current["banner"] == "https://example.invalid/a.png"
    assert ended["status"] == "已结束"
    assert ended["subtitle"] == ""  # 描述与 kind 都为空时不做假
    assert set(current) == {
        "game",
        "kind",
        "title",
        "subtitle",
        "startsAt",
        "endsAt",
        "banner",
        "status",
    }
    assert game_calendar.cache_file(directory, "starrail") == directory / "calendar-starrail.json"


def test_rows_mark_upcoming_and_truncate_long_description():
    payload = _sample(upcoming=True)
    payload["activities"][0]["description"] = "长" * 200
    rows = game_calendar.to_calendar_rows("genshin", payload, now=NOW.timestamp())
    upcoming = next(row for row in rows if row["title"] == "测试活动一")
    assert upcoming["status"] == "即将开始"
    assert len(upcoming["subtitle"]) == game_calendar.SUBTITLE_MAX + 1
    assert upcoming["subtitle"].endswith("…")


def test_status_text_treats_missing_end_as_permanent():
    start = datetime.now(tz=UTC8)
    now = start.timestamp()
    assert game_calendar.status_text(start, None, now) == "常驻"
    assert game_calendar.status_text(None, None, now) == ""
    # 没有开始时间但结束时间还没到：仍算进行中。
    assert game_calendar.status_text(None, start + timedelta(days=1), now) == "进行中"


def test_naive_iso_is_read_as_beijing_time():
    parsed = game_calendar._parse_moment("2026-10-05T12:00:00")
    assert parsed is not None and parsed.tzinfo == UTC8 and parsed.hour == 12
    assert game_calendar._parse_moment("") is None
    assert game_calendar._parse_moment("不是时间") is None


@pytest.mark.asyncio
async def test_fetch_writes_cache_and_reuses_it(tmp_path, monkeypatch):
    store = _store(tmp_path)
    seen: list[str] = []
    _patch_network(monkeypatch, {game_calendar.sra_activity.ACTIVITY_BASE + "/zzz.json": _sample()}, seen)
    first = await game_calendar.fetch("zenless", store.wiki_directory)
    assert first.source == "sra" and len(first.rows) == 2
    assert first.version == "test-1" and first.version_name == "测试版本"
    assert first.cover == "https://example.invalid/version.png"
    assert seen == ["https://starrailassistant.top/api/v1/activity/zzz.json"]
    cached = json.loads(game_calendar.cache_file(store.wiki_directory, "zenless").read_text("utf-8"))
    assert cached["schema"] == game_calendar.CACHE_SCHEMA and cached["game"] == "zenless"

    # TTL 内不再回源：把假传输层换成必然失败的，仍然拿到缓存。
    _patch_network(monkeypatch, {}, seen)
    second = await game_calendar.fetch("zenless", store.wiki_directory)
    assert second.source == "cache" and len(second.rows) == 2
    assert "缓存" in second.message
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_fetch_status_uses_injected_now(tmp_path, monkeypatch):
    """now 必须同时决定状态文案；只影响缓存判定会让注入时间半生效。"""
    store = _store(tmp_path)
    url = game_calendar.sra_activity.ACTIVITY_BASE + "/zzz.json"
    _patch_network(monkeypatch, {url: _sample()})
    later = (NOW + timedelta(days=365)).timestamp()

    fresh = await game_calendar.fetch("zenless", store.wiki_directory, now=later)
    assert fresh.source == "sra"
    # 样本的活动相对真实时钟在 -2~+10 天之间，注入一年后应全部结束。
    assert {row["status"] for row in fresh.rows} == {"已结束"}

    # 缓存分支同样要按注入的时刻出状态。
    cached = await game_calendar.fetch(
        "zenless", store.wiki_directory, now=later + 60
    )
    assert cached.source == "cache"
    assert {row["status"] for row in cached.rows} == {"已结束"}


@pytest.mark.asyncio
async def test_fetch_falls_back_to_last_successful_result(tmp_path, monkeypatch):
    store = _store(tmp_path)
    url = game_calendar.sra_activity.ACTIVITY_BASE + "/ww.json"
    _patch_network(monkeypatch, {url: _sample()})
    assert (await game_calendar.fetch("wutheringwaves", store.wiki_directory)).source == "sra"

    # 让缓存过期（超过 TTL 但仍在 24 小时兜底窗内）再断网：
    # 结果是上次成功的那份，并在 message 里说明。
    path = game_calendar.cache_file(store.wiki_directory, "wutheringwaves")
    stale = json.loads(path.read_text("utf-8"))
    stale["fetched"] = time.time() - 3600.0
    _write(path, stale)
    game_calendar.clear_memory()
    _patch_network(monkeypatch, {})
    outcome = await game_calendar.fetch("wutheringwaves", store.wiki_directory)
    assert outcome.source == "stale-cache" and len(outcome.rows) == 2
    assert "SRA 暂不可用" in outcome.message and "上次成功" in outcome.message


@pytest.mark.asyncio
async def test_fetch_discards_stale_cache_older_than_a_day(tmp_path, monkeypatch):
    """超过 24 小时的兜底数据不再展示：三周前的时间表比"暂无数据"更误导。"""
    store = _store(tmp_path)
    url = game_calendar.sra_activity.ACTIVITY_BASE + "/zzz.json"
    _patch_network(monkeypatch, {url: _sample()})
    assert (await game_calendar.fetch("zenless", store.wiki_directory)).source == "sra"

    path = game_calendar.cache_file(store.wiki_directory, "zenless")
    stale = json.loads(path.read_text("utf-8"))
    stale["fetched"] = time.time() - game_calendar.STALE_MAX_SECONDS - 60.0
    _write(path, stale)
    game_calendar.clear_memory()
    _patch_network(monkeypatch, {})

    outcome = await game_calendar.fetch("zenless", store.wiki_directory)
    assert outcome.source == "none" and outcome.rows == []
    assert "24 小时" in outcome.message


@pytest.mark.asyncio
async def test_fetch_without_cache_returns_empty_rows_not_error(tmp_path, monkeypatch):
    store = _store(tmp_path)
    _patch_network(monkeypatch, {})
    outcome = await game_calendar.fetch("nte", store.wiki_directory)
    assert outcome.source == "none" and outcome.rows == []
    assert "SRA 暂不可用" in outcome.message
    assert not game_calendar.cache_file(store.wiki_directory, "nte").exists()


@pytest.mark.asyncio
async def test_fetch_ignores_corrupt_or_legacy_cache(tmp_path, monkeypatch):
    """结构不对的缓存不能被当成"上次成功结果"。"""
    store = _store(tmp_path)
    _write(game_calendar.cache_file(store.wiki_directory, "genshin"), {"activities": "坏的"})
    _write(game_calendar.cache_file(store.wiki_directory, "starrail"), {"legacy": True})
    _patch_network(monkeypatch, {})
    for game in ("genshin", "starrail"):
        outcome = await game_calendar.fetch(game, store.wiki_directory)
        assert outcome.source == "none" and outcome.rows == []


@pytest.mark.asyncio
async def test_fetch_rejects_unknown_game(tmp_path):
    with pytest.raises(ValueError):
        await game_calendar.fetch("minecraft", _store(tmp_path).wiki_directory)


@pytest.mark.asyncio
async def test_aggregate_isolates_failures(tmp_path, monkeypatch):
    """一个游戏失败只影响它自己：其它游戏照常返回。"""
    store = _store(tmp_path)
    base = game_calendar.sra_activity.ACTIVITY_BASE
    _patch_network(
        monkeypatch,
        {
            f"{base}/ys.json": _sample(),
            f"{base}/nte.json": {"activities": []},  # 空列表也是有效响应
            # sr 未登记：假传输层返回 500，走失败分支
        },
    )
    outcomes = await game_calendar.aggregate(
        ["genshin", "starrail", "nte"], store.wiki_directory
    )
    by_game = {item.game: item for item in outcomes}
    assert [item.game for item in outcomes] == ["genshin", "starrail", "nte"]
    assert len(by_game["genshin"].rows) == 2 and by_game["genshin"].source == "sra"
    assert by_game["starrail"].rows == [] and by_game["starrail"].source == "none"
    assert by_game["nte"].rows == [] and by_game["nte"].source == "sra"  # 上游确实没有活动


def test_endfield_calendar_skips_pool_without_open(tmp_path):
    """缺开始时间的卡池不能产出 startsAt 与状态都为空的残行。"""
    store = _store(tmp_path)
    index = _index_around_now()
    index["calendar"]["pools"][0].pop("open")
    _write(store.index_file, index)

    rows = store.endfield_calendar()

    assert any(row["kind"] == "activity" for row in rows)
    assert not any(row["kind"] == "gacha" for row in rows)
    assert all(row["startsAt"] and row["status"] for row in rows)


@pytest.mark.asyncio
async def test_store_endfield_prefers_local_index(tmp_path, monkeypatch):
    store = _store(tmp_path)
    _write(store.index_file, _index_around_now())
    _patch_network(monkeypatch, {})  # 索引可用时不应联网
    outcome = await store.calendar_outcomes("endfield")
    assert outcome.source == "local"
    assert any(row["kind"] == "activity" for row in outcome.rows)
    assert "本机解包索引" in outcome.message


@pytest.mark.asyncio
async def test_store_endfield_uses_sra_when_index_has_no_activities(tmp_path, monkeypatch):
    store = _store(tmp_path)
    index = fixtures.minimal_index()
    index["calendar"] = {"activities": [], "pools": []}
    _write(store.index_file, index)
    _patch_network(
        monkeypatch, {game_calendar.sra_activity.ACTIVITY_BASE + "/end.json": _sample()}
    )
    outcome = await store.calendar_outcomes("endfield")
    assert outcome.source == "sra" and len(outcome.rows) == 2
    assert "改用 SRA" in outcome.message


@pytest.mark.asyncio
async def test_store_endfield_without_index_reports_no_data(tmp_path, monkeypatch):
    store = _store(tmp_path)
    _patch_network(monkeypatch, {})
    outcome = await store.calendar_outcomes("endfield")
    assert outcome.source == "none" and outcome.rows == []
    assert "本机索引暂无活动" in outcome.message


@pytest.mark.asyncio
async def test_store_arknights_falls_back_to_local_game_table(tmp_path, monkeypatch):
    store = _store(tmp_path)
    _patch_network(monkeypatch, {})  # SRA 失败

    async def local(*, transport=None):
        return [
            {
                "game": "arknights",
                "kind": "activity",
                "title": "本地表活动",
                "subtitle": "",
                "startsAt": "",
                "endsAt": "",
                "banner": "",
                "status": "进行中",
            }
        ]

    monkeypatch.setattr(store, "arknights_calendar", local)
    outcome = await store.calendar_outcomes("arknights")
    assert outcome.source == "local"
    assert [row["title"] for row in outcome.rows] == ["本地表活动"]
    assert "本机解包游戏表" in outcome.message


@pytest.mark.asyncio
async def test_store_arknights_uses_sra_cache_without_fallback(tmp_path, monkeypatch):
    store = _store(tmp_path)
    base = game_calendar.sra_activity.ACTIVITY_BASE
    _patch_network(monkeypatch, {f"{base}/ak.json": _sample()})
    outcome = await store.calendar_outcomes("arknights")
    assert outcome.source == "sra" and len(outcome.rows) == 2

    async def broken(*, transport=None):
        raise AssertionError("有 SRA 缓存时不应回退到解包游戏表")

    monkeypatch.setattr(store, "arknights_calendar", broken)
    _patch_network(monkeypatch, {})
    cached = await store.calendar_outcomes("arknights")
    assert cached.source == "cache" and cached.rows


@pytest.mark.asyncio
async def test_store_calendar_all_covers_every_game(tmp_path, monkeypatch):
    store = _store(tmp_path)
    _write(store.index_file, _index_around_now())
    base = game_calendar.sra_activity.ACTIVITY_BASE
    routes = {
        f"{base}/{key}.json": _sample()
        for key in ("ak", "ys", "sr", "zzz", "ww", "nte", "xtlr", "infinitynikki")
    }
    _patch_network(monkeypatch, routes)
    outcomes = await store.calendar_outcomes_all()
    by_game = {item.game: item for item in outcomes}
    assert [item.game for item in outcomes] == list(endfield_wiki.CALENDAR_GAMES)
    assert all(item.rows for item in outcomes)
    assert by_game["endfield"].source == "local"  # 终末地以本机解包索引为准
    assert by_game["genshin"].source == "sra"
    assert all(item.contract()["name"] for item in outcomes)


@pytest.mark.asyncio
async def test_store_calendar_all_rejects_unknown_game(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(endfield_wiki.WikiError):
        await store.calendar_outcomes_all(games=["genshin", "minecraft"])


@pytest.mark.asyncio
async def test_arknights_calendar_degrades_silently(tmp_path, monkeypatch):
    """回归：解包游戏表这条兜底路径仍然静默降级，不上抛。"""
    store = _store(tmp_path)

    async def broken(cache_file):
        from app.tools.akedata_client import AkedataError

        raise AkedataError("数据源请求失败：ConnectError")

    monkeypatch.setattr(game_calendar_arknights, "refresh", broken)
    assert await store.arknights_calendar() == []
