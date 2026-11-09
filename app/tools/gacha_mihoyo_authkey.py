"""米游社 Cookie 换取抽卡 authkey 的协议层。

官方 getGachaLog 只认一次性 authkey，不认 Cookie；「用米游社 Cookie 直接读记录」
的可行做法是先用米游社登录态调用 genAuthKey 换 authkey，再交给 app/tools/gacha.py
里既有的分页链路。本模块只做请求构造与响应解析，I/O 走传入的 httpx.AsyncClient。

协议依据（2026-11 核对以下仍在维护的开源实现，本链路尚未用真实账号验收）：
- POST https://api-takumi.mihoyo.com/binding/api/genAuthKey
  BTMuli/TeyvatGuide src/request/takumiReq.ts（DS 用 LK2 盐的 sign 形式，Cookie 取
  stoken+mid）、Genshin-bots/gsuid_core gsuid_core/utils/api/mys/account_request.py
  （get_authkey_by_cookie）、CMHopeSunshine/LittlePaimon LittlePaimon/utils/api.py
  （get_authkey_by_stoken）、ZZZure/ZZZ-Plugin dist/lib/mysapi/tool.js（绝区零同一个
  接口，只是 game_biz 不同）。
- 请求体 {"auth_appid": "webview_gacha", "game_biz": ..., "game_uid": int, "region": ...}
  参考 SnapHutaoRemasteringProject/Snap.Hutao.Remastered
  Web/Hoyolab/Takumi/Binding/GenAuthKeyData.cs。
- 响应 {"retcode": 0, "message": "OK", "data": {"authkey": ..., "authkey_exp": ...}}；
  上面几个实现都只读 data.authkey，所以 authkey_exp 只当作展示用的过期时间。

DS 盐与 x-rpc-app_version 一一对应，米游社换版本线时两者一起轮换，因此这里按已知
版本线由新到旧依次尝试（_SALT_LINES），并把命中的版本线记在结果里便于定位问题。
米游社更新客户端版本后需要补充这一张表。
"""

import hashlib
import random
import string
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.tools import miyoushe
from app.tools.gacha import MIHOYO

GEN_AUTHKEY_URL = "https://api-takumi.mihoyo.com/binding/api/genAuthKey"
AUTH_APPID = "webview_gacha"
# B 服（渠道服）UID 前缀，原神官方规则；见 resolve_region 的说明。
CHANNEL_UID_PREFIX = "5"

# 版本线 -> 盐。来源见模块 docstring，顺序为新到旧：盐过期时上游会拒绝签名。
_SALT_LINES: tuple[tuple[str, str], ...] = (
    ("2.117.0", "4751cb5557bfad5e249e58462c39fb0a"),
    ("2.102.1", "yBh10ikxtLPoIhgwgPZSv5dmfaOTSJ6a"),
    ("2.60.1", "1OJyMNCqFlstEQqqMOv0rKCIdTOoJhNt"),
    ("2.109.0", miyoushe.SALT_WEB),
)

# 上游用这两个码表示登录态本身失效；再换盐也不会成功，直接按登录失效回报。
_CREDENTIAL_RETCODES = frozenset({-100, -101})


class GachaAuthkeyError(ValueError):
    """换取 authkey 失败。文案在构造时就已脱敏，可原样回显给用户。"""


@dataclass(frozen=True, slots=True)
class GachaAuthkey:
    """一次换取的结果；authkey 只在本次请求内使用，不落盘、不写日志。"""

    authkey: str
    expires_at: int
    game_biz: str
    region: str
    app_version: str


@dataclass(frozen=True, slots=True)
class _GameRule:
    game_biz: str
    region: str
    channel_region: str = ""


_GAME_RULES = {
    "genshin": _GameRule("hk4e_cn", "cn_gf01", "cn_qd01"),
    "starrail": _GameRule("hkrpg_cn", "prod_gf_cn", "prod_qd_cn"),
    "zzz": _GameRule("nap_cn", "prod_gf_cn"),
}


def resolve_region(game: str, player_uid: str, region: str = "") -> str:
    """区域取值：调用方显式指定优先，其次按 UID 判断渠道服。

    B 服 UID 以 5 开头是原神官方规则（LittlePaimon 同款判断）；崩铁照这个口径
    推断但未用真实 B 服账号验收，绝区零没有可确认的渠道服区域，一律用官服区域。
    推断不成立时用户仍可显式指定 region。
    """

    rule = _GAME_RULES[game]
    if region.strip():
        return region.strip()
    if rule.channel_region and player_uid.startswith(CHANNEL_UID_PREFIX):
        return rule.channel_region
    return rule.region


def _ds(salt: str) -> str:
    """sign 形式的 DS：md5("salt=..&t=..&r=..")，与 x-rpc-client_type=5 配套。"""

    stamp = str(int(time.time()))
    nonce = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    digest = hashlib.md5(f"salt={salt}&t={stamp}&r={nonce}".encode()).hexdigest()
    return f"{stamp},{nonce},{digest}"


def _headers(
    cookie: str, *, app_version: str, device_id: str, ds: str
) -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://webstatic.mihoyo.com",
        "Referer": "https://webstatic.mihoyo.com",
        "User-Agent": (
            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) miHoYoBBS/{app_version}"
        ),
        "x-rpc-app_version": app_version,
        "x-rpc-client_type": "5",
        "x-rpc-device_id": device_id,
        "x-rpc-channel": "miyousheluodi",
        "X-Requested-With": "com.mihoyo.hyperion",
        "Content-Type": "application/json;charset=utf-8",
        "DS": ds,
        "Cookie": cookie,
    }


def _credential_fields(cookie: str) -> tuple[str, str]:
    """返回 (可发送的 Cookie, 设备 ID)；认证字段不足时报脱敏中文错误。

    米游社换 authkey 认的是 stoken（含 stoken_v2，解析时已归一），社区签到那份
    Cookie 就是它。只有 cookie_token 的网页 Cookie 没有已验证的换取路径，网上
    公开实现（TeyvatGuide、gsuid_core、LittlePaimon）都要求 stoken。
    """

    session = miyoushe.prepare_miyoushe_session(cookie)
    cookies = session.cookies
    if not cookies.get("stoken"):
        raise GachaAuthkeyError(
            "米游社凭据里没有 stoken，无法换取抽卡 authkey：请在「游戏签到 → 米游社」"
            "重新扫码登录后重试（只含 cookie_token 的网页 Cookie 没有可用的换取接口）"
        )
    # Passport v2 的别名已经由 session 归一；只发换取所需的字段，不发一次性票据。
    fields = {"stoken": cookies["stoken"]}
    if session.uid:
        fields["stuid"] = session.uid
    if cookies.get("mid"):
        fields["mid"] = cookies["mid"]
    return "; ".join(f"{key}={value}" for key, value in fields.items()), session.device_id


def _read_code(result: object) -> tuple[int | None, str]:
    """归一上游 retcode 与 message，字段漂移一律当作「未提供」。"""

    if not isinstance(result, dict):
        return None, ""
    code = result.get("retcode")
    if isinstance(code, bool) or code is None:
        retcode = None
    else:
        try:
            retcode = int(code)
        except (TypeError, ValueError):
            retcode = None
    return retcode, str(result.get("message") or "").strip()


def _int_or_zero(value: object) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


async def _post(
    client: httpx.AsyncClient, payload: dict, headers: dict[str, str]
) -> object:
    try:
        response = await client.post(GEN_AUTHKEY_URL, json=payload, headers=headers)
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise GachaAuthkeyError(
            "米游社换取 authkey 的请求被拒绝"
            f"（HTTP {error.response.status_code}），请检查网络或代理设置"
        ) from None
    except httpx.HTTPError:
        raise GachaAuthkeyError(
            "连接米游社换取 authkey 失败，请检查网络或代理设置"
        ) from None
    try:
        return response.json()
    except ValueError:
        raise GachaAuthkeyError(
            "米游社换取 authkey 的响应不是 JSON，请稍后重试"
        ) from None


async def request_authkey(
    client: httpx.AsyncClient,
    *,
    game: str,
    player_uid: str,
    cookie: str,
    region: str = "",
) -> GachaAuthkey:
    """用米游社 Cookie 换取指定游戏与角色的一次性抽卡 authkey。

    失败一律抛 GachaAuthkeyError，消息里只有版本线与上游 retcode，
    不含 Cookie 与 authkey 本身。
    """

    rule = _GAME_RULES.get(game)
    if rule is None:
        raise GachaAuthkeyError(
            "按米游社 Cookie 读取记录只支持原神、崩坏：星穹铁道与绝区零"
        )
    uid = str(player_uid or "").strip()
    if not uid.isdigit():
        raise GachaAuthkeyError("按米游社 Cookie 读取记录需要填写纯数字的游戏 UID")
    raw_cookie = str(cookie or "").strip()
    if not raw_cookie:
        raise GachaAuthkeyError(
            "所选账号没有米游社登录凭据：请先在「游戏签到 → 米游社」扫码登录，"
            "或在这次请求里粘贴米游社 Cookie"
        )
    header_cookie, device_id = _credential_fields(raw_cookie)
    target_region = resolve_region(game, uid, region)
    payload = {
        "auth_appid": AUTH_APPID,
        "game_biz": rule.game_biz,
        "game_uid": int(uid),
        "region": target_region,
    }
    attempts: list[str] = []
    for app_version, salt in _SALT_LINES:
        headers = _headers(
            header_cookie,
            app_version=app_version,
            device_id=device_id,
            ds=_ds(salt),
        )
        result = await _post(client, payload, headers)
        retcode, _ = _read_code(result)
        if retcode == 0:
            data = result.get("data") if isinstance(result, dict) else None
            authkey = data.get("authkey") if isinstance(data, dict) else None
            if not isinstance(authkey, str) or not authkey:
                raise GachaAuthkeyError(
                    "米游社没有返回可用的抽卡 authkey（返回结构异常），请稍后重试"
                )
            return GachaAuthkey(
                authkey=authkey,
                expires_at=_int_or_zero(data.get("authkey_exp")),
                game_biz=rule.game_biz,
                region=target_region,
                app_version=app_version,
            )
        attempts.append(f"{app_version}/{'未知' if retcode is None else retcode}")
        if retcode in _CREDENTIAL_RETCODES:
            raise GachaAuthkeyError("米游社登录已失效，请重新扫码登录后再试")
    raise GachaAuthkeyError(
        "米游社拒绝了换取抽卡 authkey 的请求"
        f"（尝试的版本线 {('、'.join(attempts)) or '无'}）："
        "请确认米游社登录状态是否有效，或先在游戏内打开一次抽卡记录后再试"
    )


def build_source(game: str, authkey: GachaAuthkey) -> str:
    """把 authkey 组装成官方 getGachaLog 链接，交给既有的分页链路复用。"""

    biz, path, _ = MIHOYO[game]
    query = urlencode(
        {
            "authkey": authkey.authkey,
            "authkey_ver": "1",
            "sign_type": "2",
            "game_biz": authkey.game_biz,
            "region": authkey.region,
            "lang": "zh-cn",
            "auth_appid": AUTH_APPID,
        }
    )
    return f"https://public-operation-{biz}.mihoyo.com{path}?{query}"
