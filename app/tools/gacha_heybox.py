"""小黑盒（Heybox）终末地抽卡补录的纯转换。

小黑盒的「抽卡分析」页面自己给 /game/endfield/player/overview 签名，本工具没有浏览器
运行时，所以这里只把用户粘贴的 overview 响应文本转成 GachaRecord：无 I/O、无凭据、
无网络。聚合口径、重建规则与校验参考 Priestess-bot 的 plugins/heybox_import/plan.py
（MIT），按本仓的存储模型重写；来源与许可见 NOTICE.md。

小黑盒只记得六星的确切时间与「距上一个六星的抽数」（diff）、五星的名字与个数，不记每个
四星。因此：六星用真实名字与秒级时间，五星按个数补名（段内位置未知），其余抽数按每十抽
一批铺成四星占位行（name=PLACEHOLDER_NAME）。补录行的 id 一律以 heybox: 开头，与官方行
天然分开、可整体撤销；六星是真实记录，沿用小黑盒原始 id。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.gacha import GachaRecord
from app.utils.constants import UTC8

OVERVIEW_PATH = "/game/endfield/player/overview"
TOOL_URL = "https://www.xiaoheihe.cn/game/endfield/card_statistic?user_id={}"
PLACEHOLDER_NAME = "小黑盒占位"  # 直接显示在记录表里，不能看着像角色名
PLACEHOLDER_RARITY = 4
SUPPORTED_PREFIXES = ("special", "joint", "wepon", "weapon")  # wepon 是小黑盒数据里的写法
SUPPORTED_IDS = ("standard", "beginner")
DERIVED_PREFIX = "heybox:"
MAX_IMPORT_RECORDS = 200_000  # 与持久化记录上限一致；在展开列表前拦截小体积的大数值输入。
HEYBOX_ID_PATTERN = re.compile(r"^[0-9]{4,12}$")
# 角色池的小黑盒前缀 -> 本仓 poolType（与 app/tools/gacha.py 的 END_POOLS 同构）。
CHAR_POOL_TYPES = {
    "special": "E_CharacterGachaPoolType_Special",
    "joint": "E_CharacterGachaPoolType_Joint",
    "standard": "E_CharacterGachaPoolType_Standard",
    "beginner": "E_CharacterGachaPoolType_Beginner",
}
# 池 id 前缀 -> overview 的 gacha_type_latest_seq_id 里的键（武器池统一是 weapon）。
POOL_SEQ_KEYS = (
    ("special", "E_CharacterGachaPoolType_Special"),
    ("joint", "E_CharacterGachaPoolType_Joint"),
    ("standard", "E_CharacterGachaPoolType_Standard"),
    ("beginner", "E_CharacterGachaPoolType_Beginner"),
)
# 与 app/services/endfield_wiki.py 的 ENDFIELD_MOMENTS 同一套时间串格式（这里不反向依赖服务层）。
MOMENTS = ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M")
KIND_SIX = "heybox"
KIND_FIVE = "heybox_sr"
KIND_FILL = "heybox_fill"


class HeyboxError(ValueError):
    """数据校验或协议不符：文案面向用户，只描述规则，不含原始响应内容。

    接口层把它与其它 ValueError 区分开，避免把内部校验原文回显给客户端。
    """



@dataclass(frozen=True)
class Official:
    """库里已有的一条官方记录（补录行不参与）。"""

    pool_id: str
    name: str
    rarity: int
    ts: int
    seq: int
    is_free: bool


def parse_overview(payload: str) -> dict:
    """粘贴的响应文本 -> overview 的 result；结构不符抛 ValueError。"""

    try:
        data = json.loads(payload)
    except ValueError:
        raise HeyboxError("这段内容不是小黑盒抽卡分析页的数据（不是 JSON）") from None
    if not isinstance(data, dict) or data.get("status") != "ok":
        raise HeyboxError("小黑盒返回的状态不是 ok，这不是抽卡分析页的数据")
    result = data.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("gacha_record"), list):
        raise HeyboxError("这不是小黑盒抽卡分析页的数据（缺少卡池记录）")
    if result.get("is_bind") is False or not isinstance(result.get("user_info"), dict):
        raise HeyboxError(
            "这个小黑盒 ID 没有终末地「抽卡分析」数据；请确认填的是小黑盒 ID 而不是游戏 UID，"
            "并已在小黑盒里登录终末地账号、点过一次更新"
        )
    return result


def pool_windows(index: dict) -> dict[str, tuple[int, int]]:
    """资料库索引的 calendar.pools -> {池 id: (开放, 关闭)}，unix 秒。"""

    windows: dict[str, tuple[int, int]] = {}
    calendar = (index or {}).get("calendar") or {}
    for pool in calendar.get("pools") or []:
        if not isinstance(pool, dict):
            continue
        pool_id = str(pool.get("id") or "")
        opened, closed = _moment(pool.get("open")), _moment(pool.get("close"))
        if pool_id and opened and closed and closed > opened:
            windows[pool_id] = (opened, closed)
    return windows


def heybox_records(
    result: dict,
    *,
    heybox_id: str,
    uid: str,
    official: list[GachaRecord],
    windows: dict[str, tuple[int, int]] | None = None,
) -> tuple[list[GachaRecord], list[str], list[str]]:
    """overview 的 result -> (补录记录, warnings, skipped)。

    硬校验失败整单拒绝（抛 ValueError，调用方不落库）：小黑盒 ID 形状、UID 归属、
    sum(diff)+current_pity==total_count、与已有官方六星的多重集一致。
    软失败只记 skipped：rerun 池、白名单外的池、以及无法确定时间的池。
    """

    if not HEYBOX_ID_PATTERN.fullmatch(heybox_id):
        raise HeyboxError("小黑盒 ID 应为 4-12 位数字")
    if str((result.get("user_info") or {}).get("uid") or "") != str(uid):
        raise HeyboxError("小黑盒数据里的游戏 UID 与填写的 UID 不一致，不能导入别人的记录")

    rows = [
        item
        for item in official
        if item.game == "endfield"
        and item.playerUid == str(uid)
        and not item.id.startswith(DERIVED_PREFIX)
    ]
    by_pool: dict[str, list[Official]] = {}
    by_name: dict[str, set[str]] = {}
    for item in rows:
        by_pool.setdefault(item.poolType, []).append(_official(item))
        if item.poolName:
            by_name.setdefault(_name_key(item.poolName), set()).add(item.poolType)
    account_start = _moment_seconds(
        _stamp((result.get("statistic_info") or {}).get("count_time"))
    )
    windows = windows or {}
    records: list[GachaRecord] = []
    warnings: list[str] = []
    skipped: list[str] = []
    used: set[str] = set()
    seen: Counter[tuple[int, str, int]] = Counter()
    for category in result.get("gacha_record") or []:
        if not isinstance(category, dict):
            continue
        weapon = category.get("gacha_type") == "weapon"
        for pool in category.get("pool_records") or []:
            if not isinstance(pool, dict):
                continue
            pool_id = str(pool.get("pool_id") or "")
            pool_name = str(pool.get("pool_name") or pool_id)
            lowered = pool_id.lower()
            everything = list(pool.get("records") or []) + list(
                pool.get("free_records") or []
            )
            if not _owned_by(everything, str(uid)):
                raise HeyboxError("小黑盒返回的记录里出现了其他 UID，已拒绝导入")
            if lowered.startswith("rerun"):
                # 重构寻访在官方记录里还很完整，不需要补录。
                skipped.append(
                    f"未导入『{pool_name}』：重构寻访，官方记录已完整同步，无需导入"
                )
                continue
            if not (lowered.startswith(SUPPORTED_PREFIXES) or lowered in SUPPORTED_IDS):
                skipped.append(f"未导入『{pool_name}』：暂不支持的卡池类型")
                continue
            pool_type, warning = _pool_type(pool_id, pool_name, weapon, by_name)
            if warning:
                warnings.append(warning)
            known = by_pool.get(pool_type) or []
            if known:
                # 只拿小黑盒快照（gacha_type_latest_seq_id）之内的官方行做比对：
                # 快照之后的抽数小黑盒还不知道，拿它比对会把「更新不及时」误判成数据冲突。
                snapshot = _snapshot_seq(result, pool_id, weapon)
                if snapshot is not None:
                    known = [row for row in known if row.seq <= snapshot]
                if not known:
                    skipped.append(
                        f"未导入『{pool_name}』：小黑盒快照早于已有官方记录，请先在小黑盒里更新后再导入"
                    )
                    continue
            events, reason = _pool_events(
                pool, known, weapon, windows.get(pool_id), account_start,
                max_records=MAX_IMPORT_RECORDS - len(records),
            )
            if reason:
                skipped.append(f"未导入『{pool_name}』：{reason}")
            for event in events:
                # 派生行 id 用「池 + 秒级时间 + 同秒同名的第几条」，不能用列表下标：
                # 库里已有六星时小黑盒不再重发这颗六星，下标会整体错位，重复导入就会认成新行。
                slot = seen[(event["ts"], event["name"], event["rarity"])]
                seen[(event["ts"], event["name"], event["rarity"])] += 1
                record_id = str(
                    event.get("id")
                    or f"{DERIVED_PREFIX}{heybox_id}:{pool_id}:{event['ts']}:{slot}"
                )
                if event["kind"] == KIND_FIVE:
                    # 同秒的不同五星与四星占位各自从 slot=0 计数，必须带名称命名空间。
                    label = hashlib.sha256(event["name"].encode()).hexdigest()[:16]
                    record_id += f":sr:{label}"
                if record_id in used:
                    raise HeyboxError("小黑盒数据里有重复的记录标识，无法去重")
                used.add(record_id)
                records.append(
                    GachaRecord(
                        game="endfield",
                        playerUid=str(uid),
                        id=record_id,
                        poolType=pool_type,
                        poolName=pool_name,
                        name=event["name"],
                        itemType="武器" if weapon else "角色",
                        rarity=event["rarity"],
                        time=_text(event["ts"]),
                        isFree=event["is_free"],
                        kind=event["kind"],
                    )
                )
    return records, _unique(warnings), skipped


def _official(item: GachaRecord) -> Official:
    return Official(
        pool_id=item.poolType,
        name=item.name,
        rarity=item.rarity,
        ts=_moment_seconds(item.time),
        seq=_seq(item.id),
        is_free=item.isFree,
    )


def _pool_type(
    pool_id: str, pool_name: str, weapon: bool, by_name: dict[str, set[str]]
) -> tuple[str, str]:
    """小黑盒的池 -> 本仓 poolType；武器池按池名对齐官方，对不上才单列。"""

    if not weapon:
        for prefix, pool_type in CHAR_POOL_TYPES.items():
            if pool_id.lower().startswith(prefix):
                return pool_type, ""
        return pool_id, ""
    matched = sorted(by_name.get(_name_key(pool_name), set()))
    if len(matched) == 1:
        return matched[0], ""
    return (
        pool_id,
        f"武器卡池『{pool_name}』的小黑盒编号与官方不同源，补录行会单列在『{pool_id}』下",
    )


def _pool_events(
    pool: dict,
    official: list[Official],
    weapon: bool,
    window: tuple[int, int] | None = None,
    account_start: int = 0,
    *,
    max_records: int = MAX_IMPORT_RECORDS,
) -> tuple[list[dict], str]:
    """一个池里官方还不具有的抽数，从旧到新；返回空的原因放在第二个返回值。"""

    entries = _six_stars(pool.get("records") or [])
    pity = int(pool.get("current_pity") or 0)
    total = int(pool.get("total_count") or 0)
    intervals = [int(entry.get("diff") or 0) for entry in entries]
    if pity < 0 or total < 0 or any(diff < 1 for diff in intervals):
        raise HeyboxError("小黑盒数据包含无效抽数，请更新数据后再导入")
    if sum(intervals) + pity != total:
        raise HeyboxError(
            "小黑盒数据自身对不上（六星间隔与总抽数不符），请先在小黑盒里更新后再导入"
        )
    # 免费十连也会展开，不能等生成完几十万行后才由存储层限制。
    if total + 10 * len(pool.get("free_records") or []) > max_records:
        raise HeyboxError("单次小黑盒补录超过 20 万条，请缩小导入范围")
    paid = sorted(
        (row for row in official if not row.is_free), key=lambda row: (row.ts, row.seq)
    )
    events: list[dict] = []
    if not paid:
        prev = None
        for entry in entries:
            _segment(events, entry, int(entry["diff"]) - 1, prev, weapon)
            prev = entry
        if prev is not None:
            _segment(events, None, pity, prev, weapon)
        elif pity:
            # 一个六星都没有：只能用池子的开放时间锚定。
            start = _opening(pool, window, account_start)
            if start <= 0:
                return [], "这个卡池没有出过六星，也查不到卡池开放时间，无法确定抽卡时间"
            events += [
                {
                    "ts": ts,
                    "name": PLACEHOLDER_NAME,
                    "rarity": PLACEHOLDER_RARITY,
                    "is_free": False,
                    "kind": KIND_FILL,
                }
                for ts in _spread(pity, start, None)
            ]
    else:
        first_ts = paid[0].ts
        if not any(entry["ts"] < first_ts for entry in entries) and total <= len(paid):
            return [], ""  # 小黑盒没有比已有官方行更早的数据
        ours = Counter((row.name, row.ts) for row in paid if row.rarity == 6)
        theirs = Counter(
            (entry["name"], entry["ts"])
            for entry in entries
            if entry["ts"] >= first_ts
        )
        if theirs - ours:
            raise HeyboxError(
                "小黑盒的六星记录与已有官方记录对不上，请先在小黑盒里更新后再导入"
            )
        if ours - theirs:
            raise HeyboxError("小黑盒的数据比已有的旧，请先在小黑盒里更新后再导入")
        older = [entry for entry in entries if entry["ts"] < first_ts]
        overlap = [entry for entry in entries if entry["ts"] >= first_ts]
        if overlap:
            # 与官方重叠的第一个六星：它在小黑盒里的 diff 减去官方已数到的抽数，就是缺的。
            target = overlap[0]
            row = next(
                item
                for item in paid
                if item.rarity == 6
                and (item.name, item.ts) == (target["name"], target["ts"])
            )
            have = sum(1 for item in paid if (item.ts, item.seq) <= (row.ts, row.seq))
            missing = int(target["diff"]) - have
        else:
            missing = pity - len(paid)
        if missing < 0:
            raise HeyboxError("小黑盒的数据比已有的旧，请先在小黑盒里更新后再导入")
        prev = None
        for entry in older:
            _segment(events, entry, int(entry["diff"]) - 1, prev, weapon)
            prev = entry
        if missing:
            if overlap:
                # 这颗六星官方已经有了，补录时不再重发它；时间按它的十连位置铺开，
                # 与「库里还没有这颗六星」时的首次导入完全一致，重复导入才不会整批换 id。
                _segment(events, target, missing, prev, weapon, include_entry=False)
            else:
                carry = (9 - prev["index"]) if prev and (weapon or prev["index"] > 0) else 0
                tail = min(carry, missing)
                prev_ts = prev["ts"] if prev else None
                stamps = [prev_ts] * tail + _spread(missing - tail, prev_ts, first_ts)
                events += [
                    {
                        "ts": ts,
                        "name": PLACEHOLDER_NAME,
                        "rarity": PLACEHOLDER_RARITY,
                        "is_free": False,
                        "kind": KIND_FILL,
                    }
                    for ts in stamps
                ]
        if entries:
            # 六星之后的垫抽：current_pity 是最后一个六星之后的抽数，减去官方已经同步到的部分，
            # 才是小黑盒还不知道、需要补的行；否则带官方记录重导一次会把这批垫抽丢掉。
            last = entries[-1]
            synced = sum(1 for row in paid if row.ts > last["ts"])
            rest = pity - synced
            if rest > 0:
                _segment(events, None, rest, last, weapon)
    has_free = any(row.is_free for row in official)
    first_official = min((row.ts for row in official), default=None)
    for entry in pool.get("free_records") or []:
        if entry.get("is_free") and not _is_gift(entry) and not has_free:
            if first_official is None or _stamp(entry.get("timestamp")) < first_official:
                events += _free_segment(entry)
    return events, ""


def _segment(
    events: list[dict],
    entry: dict | None,
    fillers: int,
    prev: dict | None,
    weapon: bool,
    *,
    include_entry: bool = True,
) -> None:
    """补上一颗六星之前的 fillers 抽（entry 为 None 时是末尾的垫抽）。

    include_entry=False 用于「这颗六星官方已有」的重建：只补抽数，不重发六星。
    """

    fillers = max(0, fillers)
    five: list[str] = []
    for sr in (entry or {}).get("sr_list") or []:
        count = int(sr.get("count") or 0)
        if count < 0:
            raise HeyboxError("小黑盒数据包含无效五星数量，请更新数据后再导入")
        if sr.get("name"):
            # 先截数量再展开，不能构建任意大列表后才切片。
            five.extend([sr["name"]] * min(count, fillers - len(five)))
        if len(five) == fillers:
            break
    labels = [(name, 5, KIND_FIVE) for name in five] + [
        (PLACEHOLDER_NAME, PLACEHOLDER_RARITY, KIND_FILL)
    ] * (fillers - len(five))
    prev_ts = prev["ts"] if prev else None
    carry = (
        (9 - prev["index"]) if prev and (weapon or prev["index"] > 0) else 0
    )  # 上一批十连里剩下的位置
    if entry is not None and prev is not None and entry["ts"] == prev_ts:
        stamps = [prev_ts] * fillers  # 同一个十连里的两颗六星
    else:
        tail = min(carry, fillers)
        head = min(entry["index"], fillers - tail) if entry is not None else 0
        middle = fillers - tail - head
        stamps = (
            [prev_ts] * tail
            + _spread(middle, prev_ts, entry["ts"] if entry is not None else None)
            + ([entry["ts"]] * head if entry else [])
        )
    for (name, rarity, kind), ts in zip(labels, stamps):
        events.append(
            {"ts": ts, "name": name, "rarity": rarity, "is_free": False, "kind": kind}
        )
    if entry is not None and include_entry:
        events.append(
            {
                "ts": entry["ts"],
                "name": entry["name"],
                "rarity": 6,
                "is_free": False,
                "kind": KIND_SIX,
                "id": str(entry.get("id") or ""),
            }
        )


def _free_segment(entry: dict) -> list[dict]:
    """免费十连：同一秒十行，六星（如果有）落在它自报的 diff 位。"""

    ts = _stamp(entry.get("timestamp"))
    events = [
        {
            "ts": ts,
            "name": PLACEHOLDER_NAME,
            "rarity": PLACEHOLDER_RARITY,
            "is_free": True,
            "kind": KIND_FILL,
        }
        for _ in range(10)
    ]
    if entry.get("name"):
        slot = max(1, min(10, int(entry.get("diff") or 10))) - 1
        events[slot] = {
            "ts": ts,
            "name": entry["name"],
            "rarity": 6,
            "is_free": True,
            "kind": KIND_SIX,
            "id": str(entry.get("id") or ""),
        }
    return events


def _six_stars(entries: list) -> list[dict]:
    """真实六星，从旧到新，拆出秒级时间与 id 里的序号（赠送潜能/武器不算抽数）。"""

    result = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("name") or _is_gift(entry):
            continue
        parts = str(entry.get("id") or "").split("_")
        index = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        if not 0 <= index <= 9:
            raise HeyboxError("小黑盒记录的十连位置无效，请更新数据后再导入")
        result.append(
            {**entry, "ts": _stamp(entry.get("timestamp")), "index": index}
        )
    return sorted(result, key=lambda entry: (_stamp_raw(entry), entry["index"]))


def _is_gift(entry: dict) -> bool:
    """小黑盒会在抽数旁边列里程碑赠送，它们不是抽数。"""

    return bool(
        entry.get("is_free_potential") or entry.get("is_free_weapon_or_box")
    )


def _owned_by(entries: list, uid: str) -> bool:
    return all(
        str(entry.get("id", "")).startswith(f"{uid}_")
        for entry in entries
        if isinstance(entry, dict) and (entry.get("name") or entry.get("is_free"))
    )


def _spread(count: int, after: int | None, before: int | None) -> list[int]:
    """count 个占位抽的时间：每十抽一批，严格落在两个已知时间之间。"""

    groups = -(-count // 10)
    stamps: list[int] = []
    for group in range(groups):
        if after is not None and before is not None:
            ts = after + max(1, (before - after) * (group + 1) // (groups + 1))
            ts = min(ts, before - 1) if before - after > 1 else after
        elif before is not None:
            ts = before - 60 * (groups - group)
        else:
            ts = (after or 0) + 60 * (group + 1)
        size = count - 10 * (groups - 1) if group == 0 else 10  # 短的那批是最旧的
        stamps += [ts] * size
    return stamps


def _opening(pool: dict, window: tuple[int, int] | None, account_start: int) -> int:
    """池子开放时间（unix 秒）；小黑盒的 start_time 常在窗口外，那就用资料库窗口。"""

    start = _stamp((pool.get("pool_info") or {}).get("start_time"))
    if window:
        return start if window[0] <= start < window[1] else window[0]
    return start if start > 0 else account_start


def _snapshot_seq(result: dict, pool_id: str, weapon: bool) -> int | None:
    """小黑盒见过的该类池最新官方 seqId，无法判断时返回 None。"""

    key = "weapon" if weapon else next(
        (name for prefix, name in POOL_SEQ_KEYS if pool_id.lower().startswith(prefix)),
        "",
    )
    value = (result.get("gacha_type_latest_seq_id") or {}).get(key)
    try:
        seq = int(value)
    except (TypeError, ValueError):
        return None
    return seq if seq > 0 else None


def _stamp(value: Any) -> int:
    """毫秒或秒时间戳 -> unix 秒。"""

    try:
        stamp = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return stamp // 1000 if stamp > 100_000_000_000 else stamp


def _stamp_raw(entry: dict) -> int:
    try:
        return int(entry.get("timestamp") or 0)
    except (TypeError, ValueError):
        return 0


def _moment(value: Any) -> int:
    """资料库时间串 -> unix 秒；语义与 app/services/endfield_wiki.py 的 parse_moment 一致。"""

    if not isinstance(value, str) or not value.strip():
        return 0
    text = value.strip().replace("T", " ")
    for fmt in MOMENTS:
        try:
            return int(
                datetime.strptime(text[: len(fmt) + 5], fmt)
                .replace(tzinfo=UTC8)
                .timestamp()
            )
        except ValueError:
            continue
    return 0


def _moment_seconds(value: str) -> int:
    """记录里的 "YYYY-MM-DD HH:MM:SS" -> unix 秒（北京时间）。"""

    text = str(value or "").strip().replace("T", " ")
    try:
        return int(datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC8).timestamp())
    except ValueError:
        return 0


def _text(ts: int) -> str:
    return datetime.fromtimestamp(max(0, ts), tz=UTC8).strftime("%Y-%m-%d %H:%M:%S")


def _seq(record_id: str) -> int:
    text = str(record_id or "")
    return int(text) if text.isdigit() else 0


def _name_key(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
