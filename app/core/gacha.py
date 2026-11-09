"""抽卡读取与存储编排；授权材料只留在本次请求。"""

import asyncio
import json
import time
from collections import defaultdict

from app.core.state import state
from app.models.gacha import GachaRecord
from app.services.endfield_wiki import wiki as endfield_wiki
from app.services.network import network
from app.tools import gacha as protocol
from app.tools import gacha_heybox as heybox
from app.tools import gacha_mihoyo_authkey as authkey_protocol
from app.tools.gacha_heybox import HeyboxError as HeyboxError
from app.tools.gacha_mihoyo_authkey import GachaAuthkeyError as GachaAuthkeyError
from app.version import VERSION

_fetch_lock = asyncio.Lock()
ARCHIVES = {"hk4e": "genshin", "hkrpg": "starrail", "nap": "zzz"}


def record_key(item: GachaRecord) -> tuple[str, str, str, str]:
    return item.game, item.playerUid, item.poolType, item.id


def is_derived(record: GachaRecord) -> bool:
    """小黑盒补录的派生行（四星占位、五星补名）；六星是真实记录，不算派生。"""

    return record.id.startswith(heybox.DERIVED_PREFIX)


def _store(candidate, records: list[GachaRecord]) -> int:
    """把记录并入候选状态（按 record_key 覆盖去重），返回新增条数。"""

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
    return len(existing) - before


async def merge(records: list[GachaRecord]) -> int:
    added = 0

    def update(candidate):
        nonlocal added
        added = _store(candidate, records)

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
                    client,
                    source,
                    player_uid,
                    max_pages=max_pages,
                    credential=state.require_account(account_id).SklandToken
                    if not source.strip()
                    else "",
                )
        added = await merge(records) if records else 0
        if not records and warnings:
            raise ValueError("没有取得有效抽卡记录，请检查授权时效后重试")
        return added, len(records), warnings


async def fetch_mihoyo_by_cookie(
    game: str,
    *,
    player_uid: str,
    account_id: str = "",
    cookie: str = "",
    region: str = "",
    timezone: int = 8,
    max_pages: int = 100,
) -> tuple[int, int, list[str]]:
    """用米游社登录态换一次性 authkey 后读取官方记录。

    官方接口只认 authkey：先按 game/UID/区域换 authkey，再复用 fetch_mihoyo 的
    分页链路。Cookie 只在本进程内用于换取（不落盘、不写日志），未传时复用所选
    账号组里已保存的米游社凭据（社区签到扫码绑定的那一份）。
    """

    if game not in protocol.MIHOYO:
        raise authkey_protocol.GachaAuthkeyError(
            "按米游社 Cookie 读取记录只支持原神、崩坏：星穹铁道与绝区零"
        )
    if _fetch_lock.locked():
        raise ValueError("抽卡记录正在读取，请稍后重试")
    async with _fetch_lock:
        credential = cookie.strip()
        if not credential and account_id:
            credential = str(state.require_account(account_id).MiyousheToken or "")
        async with network.client(
            proxy=state.proxy, trust_env=False, timeout=25, follow_redirects=False
        ) as client:
            grant = await authkey_protocol.request_authkey(
                client,
                game=game,
                player_uid=player_uid,
                cookie=credential,
                region=region,
            )
            records, warnings = await protocol.fetch_mihoyo(
                client,
                game,
                authkey_protocol.build_source(game, grant),
                timezone=timezone,
                max_pages=max_pages,
            )
        added = await merge(records) if records else 0
        if not records and warnings:
            raise ValueError(
                "没有取得有效抽卡记录，请检查游戏 UID 与米游社登录状态后重试"
            )
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


async def import_heybox(
    game: str, heybox_id: str, player_uid: str, payload: str
) -> tuple[int, int, list[str], list[str]]:
    """粘贴的小黑盒 overview 响应 -> 补录记录，替换该 UID 之前的补录行。

    转换在 app/tools/gacha_heybox.py 里完成，全部硬校验通过后才会落库，所以任何一条
    校验失败都不会改动现有记录。写库仍走一次 CommunityState.mutate：先摘掉这个 UID
    已有的派生行，再按 merge() 的口径并入新行（record_key 去重、20 万条上限）。
    返回 (新增, 替换掉的派生行, warnings, skipped)。
    """

    if game != "endfield":
        raise ValueError("小黑盒补录目前只支持明日方舟：终末地")
    result = heybox.parse_overview(payload)
    windows = heybox.pool_windows(endfield_wiki.index())
    warnings: list[str] = []
    skipped: list[str] = []
    added = 0
    replaced = 0

    def update(candidate):
        nonlocal added, replaced, warnings, skipped
        # 持有状态锁时校验最新官方数据，避免同步/撤销并发期间用旧快照覆盖新记录。
        records, warnings, skipped = heybox.heybox_records(
            result,
            heybox_id=heybox_id,
            uid=player_uid,
            official=candidate.gacha,
            windows=windows,
        )
        imported_pools = {item.poolType for item in records}
        # added 只数「原本库里没有」的记录：派生行会先被摘掉再按同 id 写回，
        # 如果把写回也算新增，重复导入同一份数据会报成新增几十条。
        original = {record_key(item) for item in candidate.gacha}
        kept = [
            item
            for item in candidate.gacha
            if not (
                is_derived(item)
                and item.game == game
                and item.playerUid == player_uid
                and item.poolType in imported_pools
            )
        ]
        replaced = len(candidate.gacha) - len(kept)
        candidate.gacha = kept
        _store(candidate, records)
        added = sum(1 for item in records if record_key(item) not in original)

    await state.mutate(update)
    return added, replaced, warnings, skipped


async def revoke_heybox(player_uid: str, game: str = "endfield") -> int:
    """撤销这个 UID 的小黑盒补录行；只删派生行，六星真实记录保留。"""

    removed = 0

    def update(candidate):
        nonlocal removed
        kept = [
            item
            for item in candidate.gacha
            if not (
                item.game == game and item.playerUid == player_uid and is_derived(item)
            )
        ]
        removed = len(candidate.gacha) - len(kept)
        candidate.gacha = kept

    await state.mutate(update)
    return removed


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
