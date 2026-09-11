"""抽卡读取与存储编排；授权材料只留在本次请求。"""

import asyncio
import json
import time
from collections import defaultdict

from app.core.state import state
from app.models.gacha import GachaRecord
from app.services.network import network
from app.tools import gacha as protocol
from app.version import VERSION

_fetch_lock = asyncio.Lock()
ARCHIVES = {"hk4e": "genshin", "hkrpg": "starrail", "nap": "zzz"}


def record_key(item: GachaRecord) -> tuple[str, str, str, str]:
    return item.game, item.playerUid, item.poolType, item.id


async def merge(records: list[GachaRecord]) -> int:
    added = 0

    def update(candidate):
        nonlocal added
        existing = {record_key(item): item for item in candidate.gacha}
        before = len(existing)
        for item in records:
            existing[record_key(item)] = item
        if len(existing) > 200_000:
            raise ValueError("记录超过 20 万条，请先导出备份后分开管理")
        candidate.gacha = sorted(
            existing.values(),
            key=lambda item: (item.time, len(item.id), item.id),
            reverse=True,
        )
        added = len(existing) - before

    await state.mutate(update)
    return added


async def fetch(
    game: str,
    source: str,
    *,
    account_id: str,
    player_uid: str,
    timezone: int,
    max_pages: int,
) -> tuple[int, int, list[str]]:
    if _fetch_lock.locked():
        raise ValueError("抽卡记录正在读取，请稍后重试")
    async with _fetch_lock:
        async with network.client(
            proxy=state.proxy, trust_env=False, timeout=25, follow_redirects=False
        ) as client:
            if game in protocol.MIHOYO:
                records, warnings = await protocol.fetch_mihoyo(
                    client, game, source, timezone=timezone, max_pages=max_pages
                )
            elif game == "wuthering":
                records, warnings = await protocol.fetch_wuthering(client, source)
            elif game == "arknights":
                account = state.require_account(account_id)
                records, warnings = await protocol.fetch_arknights(
                    client, account.SklandToken, player_uid, max_pages=max_pages
                )
            else:
                records, warnings = await protocol.fetch_endfield(
                    client, source, player_uid, max_pages=max_pages
                )
        added = await merge(records) if records else 0
        if not records and warnings:
            raise ValueError("没有取得有效抽卡记录，请检查授权时效后重试")
        return added, len(records), warnings


async def import_records(game: str, payload: str) -> tuple[int, int, list[str]]:
    data = json.loads(payload)
    records, warnings = [], []
    if not isinstance(data, dict):
        raise ValueError("请导入 BMASC、Starward 或 UIGF JSON 文件")
    if isinstance(data.get("records"), list):
        records = [GachaRecord.model_validate(item) for item in data["records"]]
    elif any(key in data for key in ARCHIVES):
        for key, archive_game in ARCHIVES.items():
            for archive in data.get(key) or []:
                records.extend(
                    protocol.mihoyo_record(
                        archive_game,
                        item,
                        uid=str(archive["uid"]),
                        timezone=int(archive.get("timezone", 8)),
                        lang=str(archive.get("lang") or "zh-cn"),
                    )
                    for item in archive["list"]
                )
        if data.get("hk4e_ugc"):
            warnings.append(
                "文件中的千星奇域暂未纳入本次游戏范围，其余已支持游戏继续导入"
            )
    elif game in protocol.MIHOYO and isinstance(data.get("list"), list):
        info = data.get("info") or {}
        records = [
            protocol.mihoyo_record(
                game,
                item,
                uid=str(info.get("uid") or ""),
                timezone=int(info.get("region_time_zone", 8)),
                lang=str(info.get("lang") or "zh-cn"),
            )
            for item in data["list"]
        ]
    else:
        raise ValueError("文件格式不受支持；其他平台请使用 BMASC 导出格式")
    return await merge(records), len(records), warnings


def query(
    game: str,
    *,
    player_uid: str = "",
    pool: str = "",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    game_records = [item for item in state.data.gacha if item.game == game]
    selected = [
        item for item in game_records if not player_uid or item.playerUid == player_uid
    ]
    # 保底距离仅按同一角色、同类池计算；多角色选择时不混算。
    grouped = defaultdict(list)
    for item in selected:
        if item.kind != "gift_intel_book":
            pool_type = (
                "301" if game == "genshin" and item.poolType == "400" else item.poolType
            )
            grouped[(item.playerUid, pool_type)].append(item)
    pools = []
    for (uid, key), items in grouped.items():
        top = 6 if game in {"arknights", "endfield"} else 5
        pools.append(
            {
                "poolType": key,
                "poolName": f"{uid} · {items[0].poolName or key}",
                "total": len(items),
                "topRarity": top,
                "topCount": sum(item.rarity == top for item in items),
                "sinceTop": next(
                    (index for index, item in enumerate(items) if item.rarity == top),
                    len(items),
                ),
            }
        )
    filtered = [
        item
        for item in selected
        if not pool
        or item.poolType == pool
        or (game == "genshin" and pool == "301" and item.poolType == "400")
    ]
    return {
        "data": filtered[(page - 1) * page_size : page * page_size],
        "total": len(filtered),
        "players": sorted({item.playerUid for item in game_records}),
        "pools": pools,
    }


def export(game: str, player_uid: str, file_format: str) -> tuple[str, str]:
    selected = [
        item
        for item in state.data.gacha
        if item.game == game and (not player_uid or item.playerUid == player_uid)
    ]
    info = {
        "export_app": "BMASC",
        "export_app_version": VERSION,
        "export_timestamp": int(time.time()),
    }
    if file_format == "uigf":
        if game not in protocol.MIHOYO:
            raise ValueError(
                "UIGF 导出支持原神、崩铁与绝区零；其他平台请导出 BMASC JSON"
            )
        grouped = defaultdict(list)
        for item in selected:
            record = {
                "uid": item.playerUid,
                "id": item.id,
                "gacha_type": item.poolType,
                "name": item.name,
                "item_id": item.itemId,
                "item_type": item.itemType,
                "rank_type": str(item.rarity),
                "time": item.time,
                "count": "1",
                "lang": item.lang,
            }
            if game == "genshin":
                record["uigf_gacha_type"] = (
                    "301" if item.poolType == "400" else item.poolType
                )
            grouped[(item.playerUid, item.timezone, item.lang)].append(record)
        data = {
            "info": dict(info, version="v4.2"),
            next(key for key, value in ARCHIVES.items() if value == game): [
                {"uid": uid, "timezone": zone, "lang": lang, "list": items}
                for (uid, zone, lang), items in grouped.items()
            ],
        }
    else:
        data = {
            "info": dict(info, format="bmasc", version=1),
            "records": [item.model_dump() for item in selected],
        }
    return f"BMASC-{game}-{file_format}.json", json.dumps(
        data, ensure_ascii=False, indent=2
    )
