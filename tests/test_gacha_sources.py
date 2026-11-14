"""抽卡来源开放范围；假账号、假网络，不请求上游或读取真实存储。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import gacha
from app.main import create_app


def forbid_access(*_args, **_kwargs):
    pytest.fail("未开放的抽卡来源不应访问账号或网络")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "game", ["genshin", "starrail", "zzz", "wuthering", "endfield"]
)
async def test_account_fetch_rejected_before_access(monkeypatch, game):
    monkeypatch.setattr(gacha.state, "require_account", forbid_access)
    monkeypatch.setattr(gacha.network, "client", forbid_access)
    with pytest.raises(gacha.GachaAuthkeyError, match="仅明日方舟开放"):
        await gacha.fetch(
            game,
            " ",
            account_id="offline",
            player_uid="100001",
            timezone=8,
            max_pages=1,
        )


@pytest.mark.parametrize("mas_enabled", [True, False])
@pytest.mark.parametrize("game", ["genshin", "starrail", "zzz"])
def test_legacy_cookie_route_rejected_on_both_clients(
    tmp_path, monkeypatch, game, mas_enabled
):
    application = create_app(
        data_dir=tmp_path, start_scheduler=False, mas_enabled=mas_enabled
    )
    with TestClient(application, base_url="http://127.0.0.1") as client:
        client.headers["x-community-session"] = application.state.session_key
        monkeypatch.setattr(gacha.state, "require_account", forbid_access)
        monkeypatch.setattr(gacha.network, "client", forbid_access)
        response = client.post(
            "/api/gacha/fetch-cookie",
            json={
                "game": game,
                "playerUid": "100001",
                "accountId": "offline",
                "cookie": "offline-cookie",
            },
        )
        assert response.status_code == 400
        assert response.json()["code"] == 400
        assert "仅明日方舟开放" in response.json()["message"]
        assert "offline-cookie" not in response.text


@pytest.mark.parametrize(
    "game", ["genshin", "starrail", "zzz", "wuthering", "endfield"]
)
def test_fetch_route_cannot_bypass_source_limit(tmp_path, monkeypatch, game):
    application = create_app(data_dir=tmp_path, start_scheduler=False)
    with TestClient(application, base_url="http://127.0.0.1") as client:
        client.headers["x-community-session"] = application.state.session_key
        monkeypatch.setattr(gacha.state, "require_account", forbid_access)
        monkeypatch.setattr(gacha.network, "client", forbid_access)
        response = client.post(
            "/api/gacha/fetch", json={"game": game, "accountId": "offline"}
        )
        assert response.status_code == 400
        assert "仅明日方舟开放" in response.json()["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "game", ["genshin", "starrail", "zzz", "wuthering", "endfield"]
)
async def test_explicit_link_fetch_is_kept(monkeypatch, game):
    monkeypatch.setattr(gacha.state, "require_account", forbid_access)
    monkeypatch.setattr(
        gacha.network,
        "client",
        lambda **_: httpx.AsyncClient(transport=httpx.MockTransport(forbid_access)),
    )
    fetcher = AsyncMock(return_value=([], []))
    method = (
        "fetch_mihoyo" if game in {"genshin", "starrail", "zzz"} else f"fetch_{game}"
    )
    monkeypatch.setattr(gacha.protocol, method, fetcher)
    assert await gacha.fetch(
        game,
        "offline-official-link",
        account_id="",
        player_uid="100001",
        timezone=8,
        max_pages=1,
    ) == (0, 0, [])
    assert fetcher.await_count == 1
    assert "credential" not in fetcher.call_args.kwargs


@pytest.mark.asyncio
async def test_arknights_uses_selected_skland_account(monkeypatch):
    lookup = Mock(return_value=SimpleNamespace(SklandToken="offline-skland"))
    monkeypatch.setattr(
        gacha, "state", SimpleNamespace(proxy=None, require_account=lookup)
    )
    monkeypatch.setattr(
        gacha.network,
        "client",
        lambda **_: httpx.AsyncClient(transport=httpx.MockTransport(forbid_access)),
    )
    fetcher = AsyncMock(return_value=([], []))
    monkeypatch.setattr(gacha.protocol, "fetch_arknights", fetcher)
    assert await gacha.fetch(
        "arknights",
        "",
        account_id="chosen",
        player_uid="100001",
        timezone=8,
        max_pages=1,
    ) == (0, 0, [])
    lookup.assert_called_once_with("chosen")
    assert fetcher.call_args.args[1:] == ("offline-skland", "100001")
