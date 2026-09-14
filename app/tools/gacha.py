"""官方抽卡协议与导入转换。

米哈游协议参考 Scighost/Starward (MIT)，分页、池类型与 UIGF 兼容；
鸣潮参考 erzaozi/waves-plugin，明日方舟参考 gxy12345/arknights-plugin，
终末地参考 bhaoo/endfield-gacha。来源及许可见 NOTICE.md。
"""

import asyncio
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from urllib.parse import parse_qsl, urlsplit

import httpx

from app.models.gacha import GachaRecord
from app.tools.skland import parse_skland_credential
from app.utils.constants import UTC8

MIHOYO = {
    "genshin": ("hk4e", "/gacha_info/api/getGachaLog", (100, 200, 301, 302, 500)),
    "starrail": (
        "hkrpg",
        "/common/hkrpg_gacha_record/api/getGachaLog",
        (1, 2, 11, 12, 21, 22),
    ),
    "zzz": ("nap", "/common/gacha_record/api/getGachaLog", (1, 2, 3, 5, 102, 103)),
}
MIHOYO_WEB = {"webstatic.mihoyo.com", "webstatic-sea.hoyoverse.com", "gs.hoyoverse.com"}
END_POOLS = {
    f"E_CharacterGachaPoolType_{key}": name
    for key, name in (
        ("Special", "特许寻访"),
        ("Joint", "辉光庆典"),
        ("Standard", "基础寻访"),
        ("Beginner", "启程寻访"),
    )
}


def parse_official_url(source: str, hosts: set[str]) -> tuple[str, dict[str, str]]:
    url = urlsplit(source.strip())
    if (
        url.scheme != "https"
        or url.hostname not in hosts
        or url.port not in (None, 443)
        or url.username
        or url.password
    ):
        raise ValueError("请填写受支持的官方抽卡记录链接")
    query = url.query
    if "?" in url.fragment:
        query += "&" + url.fragment.split("?", 1)[1]
    return url.hostname, dict(parse_qsl(query, keep_blank_values=True))


async def api_data(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    payload: dict | None = None,
    headers: dict | None = None,
    code_key: str = "code",
    require_data: bool = True,
):
    response = await client.request(
        "POST" if payload is not None else "GET",
        url,
        params=params,
        json=payload,
        headers=headers,
    )
    response.raise_for_status()
    result = response.json()
    if (
        not isinstance(result, dict)
        or result.get(code_key) != 0
        or (require_data and result.get("data") is None)
    ):
        raise ValueError("官方记录接口未返回有效数据，请检查链接时效或角色授权")
    return result.get("data")


def mihoyo_record(
    game: str,
    item: dict,
    *,
    uid: str = "",
    timezone: int = 8,
    pool: str = "",
    lang: str = "zh-cn",
) -> GachaRecord:
    return GachaRecord(
        game=game,
        playerUid=str(item.get("uid") or uid),
        id=str(item.get("id") or ""),
        poolType=str(item.get("gacha_type") or item.get("real_gacha_type") or pool),
        name=str(item.get("name") or ""),
        itemId=str(item.get("item_id") or ""),
        itemType=str(item.get("item_type") or ""),
        rarity=int(item.get("rank_type") or 0),
        time=str(item.get("time") or ""),
        timezone=timezone,
        lang=str(item.get("lang") or lang),
    )


async def fetch_mihoyo(
    client: httpx.AsyncClient, game: str, source: str, *, timezone: int, max_pages: int
) -> tuple[list[GachaRecord], list[str]]:
    biz, path, pools = MIHOYO[game]
    cn_host = f"public-operation-{biz}.mihoyo.com"
    os_host = f"public-operation-{biz}-sg.hoyoverse.com"
    host, query = parse_official_url(source, MIHOYO_WEB | {cn_host, os_host})
    if not query.get("authkey"):
        raise ValueError("抽卡链接缺少 authkey，请复制完整记录链接")
    # 重建固定官方地址，不请求用户提交的路径、不跟随重定向。
    endpoint = f"https://{os_host if host.endswith('hoyoverse.com') else cn_host}{path}"
    parameters = {
        key: value
        for key, value in query.items()
        if key
        in {
            "authkey",
            "authkey_ver",
            "sign_type",
            "game_biz",
            "lang",
            "region",
            "auth_appid",
            "game_version",
        }
    }
    parameters.setdefault("authkey_ver", "1")
    parameters.setdefault("sign_type", "2")
    parameters.setdefault("lang", "zh-cn")
    records, warnings = [], []
    for pool in pools:
        end_id, seen = "0", set()
        try:
            for page in range(1, max_pages + 1):
                url = (
                    endpoint.replace("getGachaLog", "getLdGachaLog")
                    if game == "starrail" and pool in (21, 22)
                    else endpoint
                )
                data = await api_data(
                    client,
                    url,
                    params={
                        **parameters,
                        "real_gacha_type" if game == "zzz" else "gacha_type": str(pool),
                        "page": page,
                        "size": 20,
                        "end_id": end_id,
                    },
                    code_key="retcode",
                )
                batch = data.get("list") if isinstance(data, dict) else None
                if not isinstance(batch, list):
                    raise ValueError("分页数据无效")
                converted = [
                    mihoyo_record(game, item, timezone=timezone, pool=str(pool))
                    for item in batch
                ]
                records.extend(converted)
                if len(batch) < 20:
                    break
                end_id = converted[-1].id
                if end_id in seen:
                    raise ValueError("分页游标重复")
                seen.add(end_id)
                if page == max_pages:
                    warnings.append(f"卡池 {pool} 已达本次分页上限，记录可能不完整")
                else:
                    await asyncio.sleep(0.25)
        except Exception:
            warnings.append(
                f"卡池 {pool} 读取未完成；已读取的记录仍保留，可更新链接后重试"
            )
    return records, warnings


async def fetch_wuthering(
    client: httpx.AsyncClient, source: str
) -> tuple[list[GachaRecord], list[str]]:
    if source.strip().startswith("{"):
        raw = json.loads(source)
        query = {
            key: str(raw.get(key) or "")
            for key in ("playerId", "recordId", "serverId", "languageCode")
        }
    else:
        _, raw = parse_official_url(
            source,
            {
                "aki-gm-resources.aki-game.com",
                "aki-gm-resources-oversea.aki-game.net",
                "aki-gm-resources.aki-game.net",
                "gmserver-api.aki-game2.com",
                "gmserver-api.aki-game2.net",
            },
        )
        query = {
            "playerId": raw.get("player_id", ""),
            "recordId": raw.get("record_id", ""),
            "serverId": raw.get("svr_id", ""),
            "languageCode": raw.get("lang", "zh-Hans"),
        }
    if not query["playerId"] or not query["recordId"] or not query["serverId"]:
        raise ValueError(
            "鸣潮记录需要完整 playerId、recordId、serverId，请复制官方链接或请求 JSON"
        )
    endpoint = (
        "https://gmserver-api.aki-game2."
        + ("com" if query["serverId"] == "76402e5b20be2c39f095a152090afddc" else "net")
        + "/gacha/record/query"
    )
    records, warnings = [], []
    for pool in range(1, 8):
        try:
            batch = await api_data(
                client,
                endpoint,
                payload={
                    **query,
                    "languageCode": query["languageCode"] or "zh-Hans",
                    "cardPoolId": str(pool),
                    "cardPoolType": str(pool),
                },
            )
            if not isinstance(batch, list):
                raise ValueError("记录格式无效")
            occurrences = defaultdict(int)
            for item in reversed(batch):
                identity = json.dumps(
                    [pool, item.get("time"), item.get("name"), item.get("resourceId")],
                    ensure_ascii=False,
                )
                occurrences[identity] += 1
                # 官方没有稳定逐抽 ID。同秒同物品保留出现次数，避免十连被误合并。
                record_id = hashlib.sha256(
                    f"{identity}:{occurrences[identity]}".encode()
                ).hexdigest()
                records.append(
                    GachaRecord(
                        game="wuthering",
                        playerUid=query["playerId"],
                        id=record_id,
                        poolType=str(pool),
                        name=str(item.get("name") or ""),
                        itemId=str(item.get("resourceId") or ""),
                        itemType=str(item.get("resourceType") or ""),
                        rarity=int(item.get("qualityLevel") or 0),
                        time=str(item.get("time") or ""),
                    )
                )
            await asyncio.sleep(0.25)
        except Exception:
            warnings.append(f"鸣潮卡池 {pool} 读取未完成，请检查链接是否过期")
    return records, warnings


def hg_record(
    game: str, uid: str, item: dict, *, pool: str, pool_name: str = ""
) -> GachaRecord:
    stamp = int(item["gachaTs"])
    moment = datetime.fromtimestamp(
        stamp / (1000 if stamp > 10_000_000_000 else 1), tz=UTC8
    ).strftime("%Y-%m-%d %H:%M:%S")
    return GachaRecord(
        game=game,
        playerUid=uid,
        id=str(item.get("seqId") or f"{stamp}:{item['pos']}"),
        poolType=pool,
        poolName=str(item.get("poolName") or pool_name),
        name=str(item.get("charName") or item.get("weaponName") or ""),
        itemId=str(item.get("charId") or item.get("weaponId") or ""),
        itemType="武器" if item.get("weaponId") else "角色",
        rarity=int(item["rarity"]) + (1 if game == "arknights" else 0),
        time=moment,
        isFree=bool(item.get("isFree", False)),
        kind=str(item.get("kind") or ""),
    )


async def skland_role_token(
    client: httpx.AsyncClient, credential: str, uid: str
) -> tuple[str, str]:
    """用通行证 OAuth Token 换取指定游戏角色的临时授权。"""
    token = parse_skland_credential(credential)["oauthToken"]
    if not token or not uid:
        raise ValueError("需要含 OAuth Token 的森空岛账号及游戏 UID")
    grant = await api_data(
        client,
        "https://as.hypergryph.com/user/oauth2/v2/grant",
        payload={"appCode": "be36d44aa36bfb5b", "token": token, "type": 1},
        code_key="status",
    )
    role = await api_data(
        client,
        "https://binding-api-account-prod.hypergryph.com/account/binding/v1/u8_token_by_uid",
        payload={"uid": uid, "token": grant["token"]},
        code_key="status",
    )
    if not isinstance(role.get("token"), str) or not role["token"]:
        raise ValueError("角色授权响应无效")
    return token, role["token"]


async def fetch_arknights(
    client: httpx.AsyncClient, credential: str, uid: str, *, max_pages: int
) -> tuple[list[GachaRecord], list[str]]:
    token, role_token = await skland_role_token(client, credential, uid)
    await api_data(
        client,
        "https://ak.hypergryph.com/user/api/role/login",
        payload={"token": role_token},
        require_data=False,
    )
    headers = {"X-Account-Token": token, "X-Role-Token": role_token}
    categories = await api_data(
        client,
        "https://ak.hypergryph.com/user/api/inquiry/gacha/cate",
        params={"uid": uid},
        headers=headers,
    )
    if not isinstance(categories, list):
        raise ValueError("明日方舟卡池列表无效")
    records, warnings = [], []
    for category in categories[:50]:
        pool = str(category["id"])
        params = {"uid": uid, "category": pool, "size": 100}
        seen = set()
        try:
            for page in range(max_pages):
                data = await api_data(
                    client,
                    "https://ak.hypergryph.com/user/api/inquiry/gacha/history",
                    params=params,
                    headers=headers,
                )
                batch = data["list"]
                records.extend(
                    hg_record("arknights", uid, item, pool=pool) for item in batch
                )
                if not data.get("hasMore"):
                    break
                cursor = (str(batch[-1]["gachaTs"]), str(batch[-1]["pos"]))
                if cursor in seen:
                    raise ValueError("寻访分页重复")
                seen.add(cursor)
                params.update(gachaTs=cursor[0], pos=cursor[1])
                if page + 1 == max_pages:
                    warnings.append(f"明日方舟卡池 {pool} 达分页上限")
                await asyncio.sleep(0.25)
        except Exception:
            warnings.append(f"明日方舟卡池 {pool} 读取未完成")
    return records, warnings


async def fetch_endfield(
    client: httpx.AsyncClient,
    source: str,
    uid: str,
    *,
    max_pages: int,
    credential: str = "",
) -> tuple[list[GachaRecord], list[str]]:
    if source.strip():
        host, query = parse_official_url(
            source, {"ef-webview.hypergryph.com", "ef-webview.gryphline.com"}
        )
    else:
        # 森空岛通行证属于国服，国际服继续使用原有授权链接。
        _, role_token = await skland_role_token(client, credential, uid)
        host, query = (
            "ef-webview.hypergryph.com",
            {"u8_token": role_token, "server": "1"},
        )
    token = query.get("u8_token") or query.get("token")
    if not token or not uid:
        raise ValueError("终末地需要含 u8_token 的官方记录链接及角色 UID")
    server = (
        query.get("server")
        or query.get("server_id")
        or ("1" if host.endswith("hypergryph.com") else "")
    )
    if not server:
        raise ValueError("终末地国际服链接缺少 server 参数")
    params = {"token": token, "server_id": server, "lang": query.get("lang") or "zh-cn"}
    groups = [("char", {"pool_type": pool}, name) for pool, name in END_POOLS.items()]
    records, warnings = [], []
    try:
        weapons = await api_data(
            client, f"https://{host}/api/record/weapon/pool", params=params
        )
        groups.extend(
            (
                "weapon",
                {"pool_id": str(item["poolId"])},
                str(item.get("poolName") or "武器池"),
            )
            for item in weapons[:100]
        )
    except Exception:
        warnings.append("终末地武器卡池列表读取未完成")
    for kind, extra, name in groups:
        seen, cursor = set(), ""
        pool = str(next(iter(extra.values())))
        try:
            for page in range(max_pages):
                data = await api_data(
                    client,
                    f"https://{host}/api/record/{kind}",
                    params={
                        **params,
                        **extra,
                        **({"seq_id": cursor} if cursor else {}),
                    },
                )
                batch = data["list"]
                records.extend(
                    hg_record("endfield", uid, item, pool=pool, pool_name=name)
                    for item in batch
                )
                if not data.get("hasMore"):
                    break
                cursor = str(batch[-1]["seqId"])
                if not cursor or cursor in seen:
                    raise ValueError("寻访分页重复")
                seen.add(cursor)
                if page + 1 == max_pages:
                    warnings.append(f"{name} 达分页上限")
                await asyncio.sleep(0.25)
        except Exception:
            warnings.append(f"终末地 {name} 读取未完成")
    return records, warnings
