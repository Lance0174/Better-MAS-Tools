"""米游社 Cookie 换 authkey 的离线回归。

全部用 httpx.MockTransport 注入假传输层：不产生真实请求，也不使用真实凭据
（COOKIE 里的 stoken 是假值）。覆盖请求构造、authkey 传递给 getGachaLog、
上游失败的中文脱敏文案，以及没有账号凭据时的绑定提示。
"""

import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.core import gacha as core
from app.services.network import network
from app.tools import gacha_mihoyo_authkey as authkey

COOKIE = (
    "stuid=100000001; stoken=v2_fakestokenvalue; mid=fakemidvalue; cookie_token=fake"
)
AUTHKEY_OK = {
    "retcode": 0,
    "message": "OK",
    "data": {"authkey": "AK+slash/eq==", "authkey_exp": 1790000000},
}


def _offline_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False)


def _install_network(monkeypatch, handler) -> None:
    """把社区请求工厂换成假传输层，核心层链路不可能发出真实请求。"""

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        network,
        "client",
        lambda **_options: httpx.AsyncClient(transport=transport, trust_env=False),
    )


def _gacha_urls(requests: list[httpx.Request]) -> list[httpx.Request]:
    return [item for item in requests if "GachaLog" in str(item.url)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("game", "uid", "game_biz", "region"),
    [
        ("genshin", "100000001", "hk4e_cn", "cn_gf01"),
        # B 服 UID 以 5 开头：区域跟着切成 cn_qd01。
        ("genshin", "500000001", "hk4e_cn", "cn_qd01"),
        ("starrail", "100000002", "hkrpg_cn", "prod_gf_cn"),
        ("zzz", "100000003", "nap_cn", "prod_gf_cn"),
    ],
)
async def test_request_authkey_builds_official_request(game, uid, game_biz, region):
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=AUTHKEY_OK, request=request)

    async with _offline_client(handler) as client:
        grant = await authkey.request_authkey(
            client, game=game, player_uid=uid, cookie=COOKIE
        )

    (request,) = captured
    assert request.method == "POST"
    assert str(request.url) == authkey.GEN_AUTHKEY_URL
    assert json.loads(request.content) == {
        "auth_appid": "webview_gacha",
        "game_biz": game_biz,
        "game_uid": int(uid),
        "region": region,
    }
    headers = request.headers
    assert headers["x-rpc-client_type"] == "5"
    assert headers["x-rpc-app_version"] == grant.app_version
    assert "miHoYoBBS/" in headers["user-agent"]
    # sign 形式 DS：t,r,md5；r 是 6 位随机串。
    stamp, nonce, digest = headers["ds"].split(",")
    assert stamp.isdigit() and len(nonce) == 6 and len(digest) == 32
    assert "stoken=v2_fakestokenvalue" in headers["cookie"]
    assert grant.authkey == "AK+slash/eq=="
    assert grant.expires_at == 1790000000
    assert grant.game_biz == game_biz and grant.region == region


@pytest.mark.asyncio
async def test_region_override_wins_over_uid_prefix():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=AUTHKEY_OK, request=request)

    async with _offline_client(handler) as client:
        grant = await authkey.request_authkey(
            client,
            game="genshin",
            player_uid="500000001",
            cookie=COOKIE,
            region="cn_gf01",
        )

    assert grant.region == "cn_gf01"
    assert json.loads(captured[0].content)["region"] == "cn_gf01"


@pytest.mark.asyncio
async def test_core_cookie_fetch_passes_authkey_to_gachalog(monkeypatch):
    """换取到的 authkey 必须出现在后续 getGachaLog 请求上，而不是只停在内存里。"""

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        if request.url.path.endswith("/binding/api/genAuthKey"):
            return httpx.Response(200, json=AUTHKEY_OK, request=request)
        return httpx.Response(
            200, json={"retcode": 0, "data": {"list": []}}, request=request
        )

    _install_network(monkeypatch, handler)
    added, fetched, warnings = await core.fetch_mihoyo_by_cookie(
        "genshin", player_uid="100000001", cookie=COOKIE
    )

    assert (added, fetched, warnings) == (0, 0, [])
    gacha_requests = _gacha_urls(captured)
    assert gacha_requests, "没有向官方记录接口发起请求"
    first = gacha_requests[0]
    assert first.url.host == "public-operation-hk4e.mihoyo.com"
    query = parse_qs(urlsplit(str(first.url)).query)
    assert query["authkey"] == ["AK+slash/eq=="]
    assert query["region"] == ["cn_gf01"]
    assert query["game_biz"] == ["hk4e_cn"]


@pytest.mark.asyncio
async def test_upstream_rejection_is_chinese_and_hides_cookie():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={"retcode": -1, "message": "系统繁忙，请稍后重试 password=upstream-secret"},
            request=request,
        )

    async with _offline_client(handler) as client:
        with pytest.raises(authkey.GachaAuthkeyError) as error:
            await authkey.request_authkey(
                client, game="starrail", player_uid="100000002", cookie=COOKIE
            )

    message = str(error.value)
    assert "米游社拒绝了换取抽卡 authkey 的请求" in message
    assert "系统繁忙" not in message
    assert "upstream-secret" not in message
    # 盐随版本线轮换：失败时逐条尝试，版本线要写进文案便于排查。
    assert "2.117.0" in message
    assert len(captured) == len(authkey._SALT_LINES)
    for secret in ("v2_fakestokenvalue", "fakemidvalue", "cookie_token"):
        assert secret not in message


@pytest.mark.asyncio
async def test_credential_retcode_stops_retrying():
    """登录态失效时换盐没有意义：只请求一次就把登录问题报出来。"""

    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200, json={"retcode": -100, "message": "登录已失效"}, request=request
        )

    async with _offline_client(handler) as client:
        with pytest.raises(authkey.GachaAuthkeyError) as error:
            await authkey.request_authkey(
                client, game="zzz", player_uid="100000003", cookie=COOKIE
            )

    assert len(captured) == 1
    assert "登录已失效" in str(error.value)


@pytest.mark.asyncio
async def test_missing_account_cookie_points_to_game_sign():
    """没有绑定米游社账号时，提示必须指到「游戏签到 → 米游社」。"""

    with pytest.raises(authkey.GachaAuthkeyError) as error:
        await core.fetch_mihoyo_by_cookie("genshin", player_uid="100000001")

    message = str(error.value)
    assert "游戏签到" in message and "米游社" in message


@pytest.mark.asyncio
async def test_cookie_without_stoken_is_rejected():
    """只有 cookie_token 的网页 Cookie 没有已验证的换取路径，要明确说不支持。"""

    async with _offline_client(
        lambda request: httpx.Response(500, request=request)
    ) as client:
        with pytest.raises(authkey.GachaAuthkeyError) as error:
            await authkey.request_authkey(
                client,
                game="genshin",
                player_uid="100000001",
                cookie="stuid=100000001; cookie_token=onlytoken",
            )

    assert "没有 stoken" in str(error.value)


@pytest.mark.asyncio
async def test_uid_must_be_numeric():
    async with _offline_client(
        lambda request: httpx.Response(500, request=request)
    ) as client:
        with pytest.raises(authkey.GachaAuthkeyError) as error:
            await authkey.request_authkey(
                client, game="genshin", player_uid="", cookie=COOKIE
            )

    assert "纯数字的游戏 UID" in str(error.value)


def test_passport_v2_aliases_are_sent_using_genauthkey_names():
    header, _ = authkey._credential_fields(
        "stuid=100000001; stoken_v2=v2_fake; mid_v2=fake_mid; login_ticket=one-time"
    )
    assert "stoken=v2_fake" in header
    assert "mid=fake_mid" in header
    assert "stuid=100000001" in header
    assert "one-time" not in header


def test_ltoken_alone_cannot_be_used_as_stoken():
    with pytest.raises(authkey.GachaAuthkeyError, match="没有 stoken"):
        authkey._credential_fields("stuid=100000001; ltoken=fake_ltoken")
