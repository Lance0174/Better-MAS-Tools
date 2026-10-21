"""本机存储与同步编排测试：用假传输层，不访问真实网络。"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import endfield_fixtures as fixtures  # noqa: E402

from app.services import endfield_wiki  # noqa: E402
from app.tools import akedata_client, game_calendar_arknights  # noqa: E402

UTC8 = endfield_wiki.UTC8


class MemoryWikiStorage:
    def __init__(self):
        self.files: dict[str, str] = {}

    async def read(self, name: str) -> str | None:
        return self.files.get(name)

    async def write(self, name: str, text: str) -> None:
        self.files[name] = text


class FailingWikiStorage(MemoryWikiStorage):
    async def write(self, name: str, text: str) -> None:
        raise OSError("test storage unavailable")


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _empty_state_store(tmp_path: Path) -> endfield_wiki.WikiStore:
    return endfield_wiki.WikiStore(tmp_path / "data")


def _fake_transport(handler, monkeypatch):
    """把 akedata_client.http_client 换成注入 MockTransport 的等价客户端。"""
    original = akedata_client.http_client

    def fake(*, proxy=None, transport=None):
        return original(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(akedata_client, "http_client", fake)


def _ok_handler(tables: dict, version: str = "test-2", counter: list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if counter is not None:
            counter.append(url)
        if url == akedata_client.MANIFEST_URL:
            return httpx.Response(
                200,
                json={"latest": version, "versions": [dict(fixtures.VERSION, id=version)]},
            )
        if url == akedata_client.ASSET_INDEX_URL:
            return httpx.Response(200, json={"datasets": {"json": {"files": []}}})
        if url == akedata_client.MAPS_URL:
            return httpx.Response(200, json=fixtures.MAPS)
        name = url.rsplit("/", 1)[-1].removesuffix(".json")
        if name in tables:
            return httpx.Response(200, json=tables[name])
        return httpx.Response(404)

    return handler


def test_status_without_index_is_not_ready(tmp_path):
    status = _empty_state_store(tmp_path).status()
    assert status["ready"] is False
    assert status["schema"] == 0
    assert status["version"] == ""
    assert status["counts"]["characters"] == 0
    assert status["problems"] == []
    assert "同步" in status["message"]


def test_index_is_loaded_and_reloaded_when_file_changes(tmp_path):
    store = _empty_state_store(tmp_path)
    _write(store.index_file, fixtures.minimal_index())
    assert store.index()["version"] == "test-1"
    # 外部改动（mtime 与大小变化）后应自动重载，而不是一直用内存里的旧值。
    changed = fixtures.minimal_index()
    changed["version"] = "test-1-updated"
    changed["operators"]["chr_1"]["name"] = "改名后的干员"
    _write(store.index_file, changed)
    assert store.index()["version"] == "test-1-updated"
    assert store.index()["operators"]["chr_1"]["name"] == "改名后的干员"


@pytest.mark.asyncio
async def test_platform_storage_survives_store_restart(tmp_path):
    storage = MemoryWikiStorage()
    first = endfield_wiki.WikiStore(storage=storage)
    await first.initialize()
    _write(first.index_file, fixtures.minimal_index())
    await first._persist_file(first.index_file)

    restarted = endfield_wiki.WikiStore(storage=storage)
    await restarted.initialize()
    assert restarted.ready()
    assert restarted.index()["version"] == "test-1"


@pytest.mark.asyncio
async def test_sync_does_not_publish_index_when_platform_write_fails():
    store = endfield_wiki.WikiStore(storage=FailingWikiStorage())
    transport = httpx.MockTransport(_ok_handler(fixtures.base_tables()))

    result = await store.sync(force=True, transport=transport)

    assert result["ready"] is False
    assert "保存失败" in result["message"]
    assert not store.index_file.exists()


def test_ready_requires_matching_schema(tmp_path):
    store = _empty_state_store(tmp_path)
    index = fixtures.minimal_index()
    index["schema"] = akedata_client.INDEX_SCHEMA - 1
    _write(store.index_file, index)
    assert store.ready() is False
    assert "不一致" in store.status()["message"]


@pytest.mark.asyncio
async def test_sync_skips_rebuild_when_version_unchanged(tmp_path, monkeypatch):
    store = _empty_state_store(tmp_path)
    _write(store.index_file, fixtures.minimal_index())
    _write(
        store.state_file,
        {"version": "test-2", "schema": akedata_client.INDEX_SCHEMA, "synced_at": 1},
    )
    calls: list[str] = []
    _fake_transport(_ok_handler(fixtures.base_tables(), "test-2", calls), monkeypatch)
    status = await store.sync()
    assert status["ready"] is True
    assert status["message"] == "已是最新版本 test-2"
    # 只问了 manifest，没有下载任何表。
    assert calls == [akedata_client.MANIFEST_URL]


@pytest.mark.asyncio
async def test_sync_rebuilds_when_schema_is_outdated(tmp_path, monkeypatch):
    store = _empty_state_store(tmp_path)
    index = fixtures.minimal_index()
    index["schema"] = akedata_client.INDEX_SCHEMA - 1
    _write(store.index_file, index)
    _write(store.state_file, {"version": "test-1", "schema": index["schema"]})
    calls: list[str] = []
    _fake_transport(_ok_handler(fixtures.base_tables(), "test-1", calls), monkeypatch)
    status = await store.sync()
    assert status["ready"] is True
    assert status["schema"] == akedata_client.INDEX_SCHEMA
    assert len(calls) > 34  # 即使版本没变也会重建


@pytest.mark.asyncio
async def test_sync_writes_index_and_state_atomically(tmp_path, monkeypatch):
    store = _empty_state_store(tmp_path)
    _fake_transport(_ok_handler(fixtures.base_tables()), monkeypatch)
    status = await store.sync()
    assert status["ready"] is True
    assert status["counts"]["characters"] == 1
    assert status["updatedAt"].endswith("+08:00")
    # 只留下正式文件，没有临时文件或表目录。
    names = sorted(path.name for path in store.wiki_directory.iterdir())
    assert names == ["index.json", "state.json"]
    state = json.loads(store.state_file.read_text(encoding="utf-8"))
    assert state["schema"] == akedata_client.INDEX_SCHEMA
    assert state["counts"]["dungeons"] == 1


@pytest.mark.asyncio
async def test_sync_failure_keeps_previous_index(tmp_path, monkeypatch):
    store = _empty_state_store(tmp_path)
    _write(store.index_file, fixtures.minimal_index())
    before = store.index_file.read_bytes()

    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="上游错误正文不应被回显")

    _fake_transport(broken, monkeypatch)
    status = await store.sync(force=True)
    assert status["ready"] is True  # 旧索引继续可用
    assert status["version"] == "test-1"
    assert status["message"].startswith("同步未完成")
    assert "上游错误正文" not in status["message"]
    assert store.index_file.read_bytes() == before


@pytest.mark.asyncio
async def test_sync_reports_unreachable_manifest(tmp_path, monkeypatch):
    store = _empty_state_store(tmp_path)

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("连接被拒绝", request=request)

    _fake_transport(broken, monkeypatch)
    status = await store.sync()
    assert status["ready"] is False
    assert "ConnectError" in status["message"]
    assert not store.index_file.exists()


@pytest.mark.asyncio
async def test_ensure_ready_syncs_only_when_needed(tmp_path, monkeypatch):
    store = _empty_state_store(tmp_path)
    calls: list[str] = []
    _fake_transport(_ok_handler(fixtures.base_tables(), "test-2", calls), monkeypatch)
    assert await store.ensure_ready() is True
    downloads = len(calls)
    assert downloads > 34
    # 第二次已就绪，不再发起任何请求。
    assert await store.ensure_ready() is True
    assert len(calls) == downloads


@pytest.mark.asyncio
async def test_startup_sync_skips_when_index_exists(tmp_path, monkeypatch):
    store = _empty_state_store(tmp_path)
    _write(store.index_file, fixtures.minimal_index())

    def fail(*args, **kwargs):
        raise AssertionError("已有索引时不应同步")

    monkeypatch.setattr(store, "sync", fail)
    await store.startup_sync()


def test_parse_moment_accepts_index_formats():
    parsed = endfield_wiki.parse_moment("2026/01/01 04:00:00")
    assert parsed is not None and parsed.tzinfo == UTC8
    assert parsed.hour == 4
    assert endfield_wiki.parse_moment("2026-01-01 04:00:00") is not None
    assert endfield_wiki.parse_moment("") is None
    assert endfield_wiki.parse_moment(None) is None
    assert endfield_wiki.parse_moment("不是时间") is None


def test_endfield_calendar_marks_status(tmp_path):
    store = _empty_state_store(tmp_path)
    now = datetime.now(tz=UTC8)
    def stamp(delta):
        return (now + delta).strftime("%Y/%m/%d %H:%M:%S")

    index = fixtures.minimal_index()
    index["calendar"]["activities"] = [
        {"id": "a1", "name": "进行中", "open": stamp(timedelta(days=-1)), "close": stamp(timedelta(days=1)), "tab": "tab", "color": ""},
        {"id": "a2", "name": "即将开始", "open": stamp(timedelta(days=2)), "close": stamp(timedelta(days=3)), "tab": "", "color": ""},
        {"id": "a3", "name": "已结束", "open": stamp(timedelta(days=-3)), "close": stamp(timedelta(days=-2)), "tab": "", "color": ""},
    ]
    index["calendar"]["pools"] = []
    _write(store.index_file, index)
    rows = {row["title"]: row for row in store.endfield_calendar()}
    assert rows["进行中"]["status"] == "进行中"
    assert rows["即将开始"]["status"] == "即将开始"
    assert rows["即将开始"]["banner"] == ""
    assert rows["进行中"]["banner"].endswith("/activity/tab.png")


@pytest.mark.asyncio
async def test_calendar_rejects_unknown_game(tmp_path):
    # 日历扩展到多游戏后 genshin 成了合法枚举，不存在的标识才由服务层拒绝。
    with pytest.raises(endfield_wiki.WikiError):
        await _empty_state_store(tmp_path).calendar("minecraft")


@pytest.mark.asyncio
async def test_arknights_calendar_degrades_silently(tmp_path, monkeypatch):
    store = _empty_state_store(tmp_path)

    async def broken(cache_file):
        raise akedata_client.AkedataError("数据源请求失败：ConnectError")

    monkeypatch.setattr(game_calendar_arknights, "refresh", broken)
    assert await store.arknights_calendar() == []


def test_entry_reports_readable_errors(tmp_path):
    store = _empty_state_store(tmp_path)
    with pytest.raises(endfield_wiki.WikiError, match="还没有终末地资料索引"):
        store.entry("character", "chr_1")
    _write(store.index_file, fixtures.minimal_index())
    with pytest.raises(endfield_wiki.WikiError, match="没有找到这条资料"):
        store.entry("character", "missing")
    with pytest.raises(endfield_wiki.WikiError, match="不支持的资料类型"):
        store.entry("relic", "chr_1")


def test_search_uses_the_shipped_alias_table(tmp_path):
    store = _empty_state_store(tmp_path)
    _write(store.index_file, fixtures.minimal_index())
    rows = store.search("测试干员", 10)
    assert rows and rows[0]["id"] == "chr_1"
    assert store.search("", 10) == []
    assert len(store.search("测试", 1)) <= 1
