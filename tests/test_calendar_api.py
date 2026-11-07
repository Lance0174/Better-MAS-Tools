"""活动日历接口契约测试：多游戏枚举、calendar-all 聚合与逐游戏失败隔离。

用固定样本与假传输层，不访问真实网络。
"""

import json
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent))

import endfield_fixtures as fixtures  # noqa: E402

from app.main import create_app  # noqa: E402
from app.services import endfield_wiki, game_calendar  # noqa: E402
from app.services.network import network  # noqa: E402

NOW_GAMES = (
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
ROW_FIELDS = {"game", "kind", "title", "subtitle", "startsAt", "endsAt", "banner", "status"}
BASE = game_calendar.sra_activity.ACTIVITY_BASE


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _sample(version: str = "test-1") -> dict:
    return {
        "version": version,
        "versionName": f"{version} 版本",
        "cover": "https://example.invalid/version.png",
        "startTime": "2026-10-05T12:00:00",
        "endTime": "2026-11-15T03:59:59",
        "activities": [
            {
                "name": "测试限时活动",
                "kind": "限时活动",
                "description": "描述摘要",
                "startTime": "2026-10-05T12:00:00",
                "endTime": "2026-11-15T03:59:59",
                "cover": "https://example.invalid/a.png",
            }
        ],
    }


@pytest.fixture(autouse=True)
def _clean_memory():
    game_calendar.clear_memory()
    yield
    game_calendar.clear_memory()


@pytest.fixture()
def data_dir(tmp_path):
    """终末地索引留空日历，让 endfield 也走 SRA，便于统一验证接口。"""
    directory = tmp_path / "data"
    index = fixtures.minimal_index()
    index["calendar"] = {"activities": [], "pools": []}
    _write(directory / "wiki" / "index.json", index)
    _write(
        directory / "wiki" / "state.json",
        {"version": "test-1", "schema": 20, "synced_at": 1767225600, "problems": []},
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
    with TestClient(application, base_url="http://127.0.0.1") as test_client:
        test_client.headers.update({"x-community-session": application.state.session_key})
        yield test_client


def _patch_network(monkeypatch, routes: dict[str, object]) -> None:
    """按 URL 分发的假传输层；登记之外的地址一律 500（绝不落到真实网络）。"""

    def handler(request: httpx.Request) -> httpx.Response:
        payload = routes.get(str(request.url))
        if payload is None:
            return httpx.Response(500, text="上游错误正文")
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(
        network,
        "client",
        lambda **options: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _all_routes(version: str = "test-1") -> dict[str, object]:
    keys = ("end", "ak", "ys", "sr", "zzz", "ww", "nte", "xtlr", "infinitynikki")
    return {f"{BASE}/{key}.json": _sample(version) for key in keys}


def test_calendar_game_enum_covers_every_game(client, monkeypatch):
    _patch_network(monkeypatch, _all_routes())
    for game in NOW_GAMES:
        response = client.get("/api/wiki/calendar", params={"game": game})
        assert response.status_code == 200, game
        body = response.json()
        assert body["code"] == 200
        rows = body["data"]
        assert rows and all(row["game"] == game for row in rows)
        assert all(set(row) == ROW_FIELDS for row in rows)
        assert rows[0]["kind"] == "activity"
        assert rows[0]["startsAt"].endswith("+08:00")
        assert rows[0]["status"] in {"进行中", "即将开始", "已结束", "常驻"}


def test_calendar_rejects_unknown_game(client):
    assert client.get("/api/wiki/calendar", params={"game": "minecraft"}).status_code == 422


def test_calendar_single_game_reports_failure_in_message(client, monkeypatch):
    """单个游戏取不到数据时仍是 200：空列表 + message 说明，不是 500。"""
    _patch_network(monkeypatch, {})
    response = client.get("/api/wiki/calendar", params={"game": "genshin"})
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200 and body["data"] == []
    assert "SRA 暂不可用" in body["message"]


def test_calendar_all_returns_every_game_in_order(client, monkeypatch):
    _patch_network(monkeypatch, _all_routes())
    body = client.get("/api/wiki/calendar-all").json()
    assert body["code"] == 200 and body["status"] == "success"
    groups = body["data"]
    assert [group["game"] for group in groups] == list(NOW_GAMES)
    for group in groups:
        assert set(group) == {
            "game",
            "name",
            "source",
            "version",
            "versionName",
            "cover",
            "activities",
            "message",
        }
        assert group["name"]  # 中文展示名由后端给出，前端不必再维护映射
        assert group["source"] == "sra"
        assert group["version"] == "test-1" and group["versionName"] == "test-1 版本"
        assert group["cover"] == "https://example.invalid/version.png"
        assert group["message"]
        assert group["activities"]
        for row in group["activities"]:
            assert set(row) == ROW_FIELDS
            assert row["game"] == group["game"]


def test_calendar_all_keeps_failures_isolated(client, monkeypatch):
    """一个游戏取不到数据时只有它自己是空的，接口仍然 200。"""
    routes = _all_routes()
    routes.pop(f"{BASE}/zzz.json")  # 绝区零：上游 500 且没有缓存
    _patch_network(monkeypatch, routes)
    response = client.get("/api/wiki/calendar-all")
    assert response.status_code == 200
    groups = {group["game"]: group for group in response.json()["data"]}
    assert groups["zenless"]["activities"] == []
    assert groups["zenless"]["source"] == "none"
    assert "SRA 暂不可用" in groups["zenless"]["message"]
    assert groups["genshin"]["activities"] and groups["genshin"]["source"] == "sra"


def test_calendar_all_uses_cache_when_upstream_fails(client, store, monkeypatch):
    _patch_network(monkeypatch, _all_routes())
    assert client.get("/api/wiki/calendar-all").status_code == 200

    # 缓存过期（仍在 24 小时兜底窗内）+ 上游全挂：返回上次成功的结果，
    # 只是说明里点出降级。
    for game in NOW_GAMES:
        path = game_calendar.cache_file(store.wiki_directory, game)
        payload = json.loads(path.read_text("utf-8"))
        payload["fetched"] = time.time() - 3600.0
        _write(path, payload)
    game_calendar.clear_memory()
    _patch_network(monkeypatch, {})
    groups = {group["game"]: group for group in client.get("/api/wiki/calendar-all").json()["data"]}
    for game in NOW_GAMES:
        assert groups[game]["source"] == "stale-cache", game
        assert groups[game]["activities"], game
        assert "上次成功" in groups[game]["message"]
