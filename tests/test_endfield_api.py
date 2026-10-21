"""资料库与活动日历的接口契约测试；用假传输层，不访问真实网络。"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent))

import endfield_fixtures as fixtures  # noqa: E402

from app.main import create_app  # noqa: E402
from app.services import endfield_wiki  # noqa: E402
from app.tools import akedata_client, game_calendar_arknights  # noqa: E402


def _write(directory: Path, name: str, payload: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _index_around(now: datetime) -> dict:
    """把索引里的活动与卡池时间挪到当前时间附近，便于验证日历状态。"""
    index = fixtures.minimal_index()
    open_at = now - timedelta(days=1)
    close_at = now + timedelta(days=10)
    for row in (*index["calendar"]["activities"], *index["calendar"]["pools"]):
        row["open"] = open_at.strftime("%Y/%m/%d %H:%M:%S")
        row["close"] = close_at.strftime("%Y/%m/%d %H:%M:%S")
    return index


@pytest.fixture()
def data_dir(tmp_path):
    directory = tmp_path / "data"
    wiki_dir = directory / "wiki"
    _write(wiki_dir, "index.json", _index_around(datetime.now()))
    _write(
        wiki_dir,
        "state.json",
        {"version": "test-1", "schema": 20, "synced_at": 1767225600, "problems": []},
    )
    # 预置明日方舟缓存，避免接口测试触发下载。
    _write(
        wiki_dir,
        "arknights.json",
        {
            "version": "test",
            "fetched": 1767196800,
            game_calendar_arknights.GAME_ACTIVITIES_KEY: [
                {"id": "act1", "name": "测试方舟活动", "kind": "活动", "start": 1767196800, "end": 1769800000}
            ],
            "activities": [
                {"id": "act1", "name": "测试方舟活动", "kind": "活动", "start": 1767196800, "end": 1769800000}
            ],
            "pools": [
                {"id": "LIMITED1", "name": "测试寻访", "kind": "限定寻访", "up": ["干员X"], "start": 1767196800, "end": 1769800000}
            ],
            "pool_images": {"LIMITED1": "https://example.invalid/banner.png"},
        },
    )
    return directory


@pytest.fixture()
def store(data_dir, monkeypatch):
    instance = endfield_wiki.WikiStore(data_dir)
    monkeypatch.setattr(endfield_wiki, "wiki", instance)
    monkeypatch.setattr("app.api.wiki.wiki", instance)
    return instance


@pytest.fixture()
def client(data_dir, store):
    application = create_app(data_dir=data_dir, start_scheduler=False)
    # base_url 用回环地址：应用启用了 TrustedHostMiddleware。
    with TestClient(application, base_url="http://127.0.0.1") as test_client:
        test_client.headers.update(
            {"x-community-session": application.state.session_key}
        )
        yield test_client


def test_status_contract(client):
    response = client.get("/api/wiki/status")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200 and body["status"] == "success"
    data = body["data"]
    assert set(data) == {
        "ready",
        "version",
        "updatedAt",
        "schema",
        "counts",
        "problems",
        "message",
    }
    assert data["ready"] is True
    assert data["version"] == "test-1"
    assert data["schema"] == 20
    assert data["updatedAt"].startswith("2026-01-01T08:00:00")
    assert data["counts"] == {
        "characters": 1,
        "weapons": 1,
        "equipSuits": 1,
        "dungeons": 1,
        "enemies": 1,
        "activities": 1,
    }
    assert isinstance(data["problems"], list) and isinstance(data["message"], str)


def test_api_uses_explicitly_injected_wiki_store(tmp_path):
    custom_dir = tmp_path / "injected"
    _write(custom_dir / "wiki", "index.json", fixtures.minimal_index())
    store = endfield_wiki.WikiStore(custom_dir)
    application = create_app(
        start_scheduler=False, external_state=True, wiki_store=store
    )
    with TestClient(application, base_url="http://127.0.0.1") as test_client:
        test_client.headers.update(
            {"x-community-session": application.state.session_key}
        )
        response = test_client.get("/api/wiki/status")
    assert response.status_code == 200
    assert response.json()["data"]["version"] == "test-1"


def test_status_requires_session(client):
    headers = dict(client.headers)
    client.headers.pop("x-community-session")
    try:
        assert client.get("/api/wiki/status").status_code == 401
    finally:
        client.headers.update(headers)


def test_status_without_index_reports_not_ready(store, data_dir, monkeypatch):
    store.index_file.unlink()
    status = store.status()
    assert status["ready"] is False
    assert status["schema"] == 0
    assert status["counts"]["characters"] == 0
    assert "同步" in status["message"]


def test_search_contract(client):
    response = client.get("/api/wiki/search", params={"q": "测试干"})
    assert response.status_code == 200
    rows = response.json()["data"]
    assert rows and set(rows[0]) == {"kind", "id", "name", "subtitle", "icon"}
    assert rows[0]["kind"] == "character"
    assert rows[0]["id"] == "chr_1"
    assert rows[0]["icon"].endswith("/charremoteicon/icon_chr_1.png")


def test_search_finds_every_kind(client):
    found = {}
    for word in ("测试干员", "测试武器", "测试套装", "测试关卡", "测试敌人"):
        rows = client.get("/api/wiki/search", params={"q": word}).json()["data"]
        assert rows, word
        found[rows[0]["kind"]] = rows[0]["name"]
    assert set(found) == {"character", "weapon", "equipSuit", "dungeon", "enemy"}


def test_search_empty_query_and_limit_bounds(client):
    assert client.get("/api/wiki/search", params={"q": "  "}).json()["data"] == []
    assert client.get("/api/wiki/search", params={"q": "测试", "limit": 1}).status_code == 200
    assert client.get("/api/wiki/search", params={"q": "测试", "limit": 0}).status_code == 422
    assert client.get("/api/wiki/search", params={"q": "测试", "limit": 51}).status_code == 422
    assert client.get("/api/wiki/search", params={"q": "x" * 101}).status_code == 422
    rows = client.get("/api/wiki/search", params={"q": "测试", "limit": 2}).json()["data"]
    assert len(rows) <= 2


def test_entry_contract_for_character(client):
    response = client.get("/api/wiki/entry", params={"kind": "character", "id": "chr_1"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == {"kind", "id", "name", "subtitle", "icon", "tags", "sections"}
    assert data["name"] == "测试干员"
    assert data["tags"]
    assert all(set(section) <= {"title", "fields", "table"} for section in data["sections"])
    assert all(
        set(field) == {"label", "value"}
        for section in data["sections"]
        for field in section["fields"]
    )
    skill = next(s for s in data["sections"] if s["title"].startswith("技能"))
    assert skill["table"]["columns"] == ["项目", "Lv9", "M1", "M2", "M3"]
    assert all(len(row) == len(skill["table"]["columns"]) for row in skill["table"]["rows"])


def test_entry_missing_returns_readable_error(client):
    response = client.get("/api/wiki/entry", params={"kind": "character", "id": "nope"})
    assert response.status_code == 400
    assert response.json()["message"].startswith("没有找到这条资料")


def test_entry_rejects_unknown_kind(client):
    response = client.get("/api/wiki/entry", params={"kind": "relic", "id": "x"})
    assert response.status_code == 422  # kind 是 Literal，契约层直接拒绝


def test_calendar_endfield_rows(client):
    rows = client.get("/api/wiki/calendar", params={"game": "endfield"}).json()["data"]
    assert rows
    kinds = {row["kind"] for row in rows}
    assert kinds <= {"activity", "gacha"}
    for row in rows:
        assert set(row) == {
            "game",
            "kind",
            "title",
            "subtitle",
            "startsAt",
            "endsAt",
            "banner",
            "status",
        }
        assert row["game"] == "endfield"
        assert row["status"] in {"进行中", "即将开始", "已结束", "常驻", ""}
    # 活动与卡池都在进行中；活动带 tab 图，卡池列出 UP 干员。
    assert {row["status"] for row in rows} == {"进行中"}
    activity = next(row for row in rows if row["kind"] == "activity")
    assert activity["banner"] == akedata_client.activity_banner_url("tab_a1")
    pool = next(row for row in rows if row["kind"] == "gacha")
    assert pool["subtitle"] == "UP：测试干员"
    assert all(row["startsAt"].endswith("+08:00") for row in rows)


def test_calendar_arknights_falls_back_to_local_game_table(client, monkeypatch):
    """SRA 取不到（这里让它返回"无数据"）时，回退到本机的解包游戏表缓存。"""
    from app.services import game_calendar

    async def no_sra(*args, **kwargs):
        return game_calendar.CalendarOutcome(
            "arknights", [], "SRA 暂不可用，稍后重试", "none"
        )

    monkeypatch.setattr(game_calendar, "fetch", no_sra)

    def fail(*args, **kwargs):
        raise AssertionError("测试不应下载真实数据")

    monkeypatch.setattr(game_calendar_arknights, "refresh", fail)
    rows = client.get("/api/wiki/calendar", params={"game": "arknights"}).json()["data"]
    assert [row["kind"] for row in rows] == ["activity", "gacha"]
    assert all(row["game"] == "arknights" for row in rows)
    assert rows[1]["subtitle"].startswith("UP：")


def test_calendar_rejects_unknown_game(client):
    # genshin 现在是合法枚举（与 SRA 的 ys 对应），不存在的游戏才被契约层拒绝。
    assert client.get("/api/wiki/calendar", params={"game": "genshin"}).status_code == 200
    assert (
        client.get("/api/wiki/calendar", params={"game": "minecraft"}).status_code == 422
    )


def test_sync_failure_reports_readable_message(client, store, monkeypatch):
    async def fail(*args, **kwargs):
        raise akedata_client.AkedataError("数据源请求失败（https://data.akedata.wiki/manifest.json）：ConnectError")

    monkeypatch.setattr(akedata_client, "fetch_manifest", fail)
    response = client.post("/api/wiki/sync", json={"force": True})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["ready"] is True  # 旧索引继续可用
    assert data["version"] == "test-1"
    assert "同步未完成" in data["message"]
    assert "ConnectError" in data["message"]


def test_sync_rebuilds_index_through_fake_transport(client, data_dir, monkeypatch):
    """用 MockTransport 覆盖全部 HTTP：manifest、34 张表、maps 与资源清单。"""
    tables = fixtures.base_tables()
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requests.append(url)
        if url == akedata_client.MANIFEST_URL:
            return httpx.Response(
                200, json={"latest": "test-2", "versions": [dict(fixtures.VERSION, id="test-2")]}
            )
        if url == akedata_client.ASSET_INDEX_URL:
            return httpx.Response(200, json={"datasets": {"json": {"files": []}}})
        if url == akedata_client.MAPS_URL:
            return httpx.Response(200, json=fixtures.MAPS)
        name = url.rsplit("/", 1)[-1].removesuffix(".json")
        if name in tables:
            return httpx.Response(200, json=tables[name])
        return httpx.Response(404)

    original = akedata_client.http_client

    def fake_client(*, proxy=None, transport=None):
        return original(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(akedata_client, "http_client", fake_client)
    response = client.post("/api/wiki/sync", json={"force": True})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["ready"] is True
    assert data["version"] == "test-2"
    assert data["counts"]["characters"] == 1
    assert data["message"].startswith("已同步 test-2")
    # 索引与状态已原子替换写盘，临时表目录被清理。
    stored = json.loads((data_dir / "wiki" / "index.json").read_text(encoding="utf-8"))
    assert stored["version"] == "test-2"
    state = json.loads((data_dir / "wiki" / "state.json").read_text(encoding="utf-8"))
    assert state["schema"] == akedata_client.INDEX_SCHEMA
    assert not (data_dir / "wiki" / "tables_tmp").exists()
    assert len(requests) >= 36  # manifest + maps + 34 张表
