"""终末地资料库的关键词解析：昵称、简称、同音字、唯一前缀与模糊匹配。

移植自 Priestess-bot 的 plugins/endfield_wiki/lookup.py（MIT License，
Copyright (c) 2026 Billtranscend），逐条对照改写为不带 nonebot 依赖的纯解析模块。
昵称表 data/endfield_aliases.json 同源；来源与许可见 NOTICE.md。

同音字匹配由 pypinyin 提供，发布运行时会安装该依赖；可选导入用于兼容受限的
嵌入式环境。缺少时只关闭同音匹配（"黎诺" -> "梨诺"），其他匹配方式照常可用。

匹配始终保持保守：先把输入归一化为精确键，再取唯一前缀，最后才做近似纠错；
有歧义或查不到都返回 None，由调用方决定如何呈现，本模块不读写任何存储。
"""

from __future__ import annotations

import difflib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:  # 受限嵌入环境可能缺少可选依赖，此时只关闭同音匹配
    from pypinyin import Style, pinyin
except ImportError:  # pragma: no cover - 本机无该依赖时的降级分支
    Style = None  # type: ignore[assignment]
    pinyin = None  # type: ignore[assignment]

__all__ = [
    "HOMOPHONE_AVAILABLE",
    "MAX_CANDIDATES",
    "MIN_PREFIX",
    "RESULT_KINDS",
    "Result",
    "Resolver",
    "load_aliases",
    "normalize",
    "to_pinyin",
]

def _data_directory() -> Path:
    """定位随包分发的数据目录，兼容源码运行与 PyInstaller 打包含。

    PyInstaller 的 --add-data 会把数据放到 sys._MEIPASS 下，此时 __file__
    指向解包出来的模块路径，两者在 onedir 模式下通常一致，但显式判断更稳。
    """

    base = getattr(sys, "_MEIPASS", None)
    if base:
        bundled = Path(base) / "app" / "tools" / "data"
        if bundled.is_dir():
            return bundled
    return Path(__file__).resolve().parent / "data"


ALIASES_FILE = _data_directory() / "endfield_aliases.json"
HOMOPHONE_AVAILABLE = pinyin is not None

SIGNATURE_SUFFIXES = ("专武", "专属武器")
# "/庄方宜配装"：仍然是干员卡，卡上带配装统计。
BUILD_SUFFIXES = ("推荐装备", "配装", "装备", "套装")
MIN_PREFIX = 2
FUZZY_CUTOFF = 0.8
MAX_CANDIDATES = 6
# 同名变体共用资料，统一解析到首个列出的 id。
PREFERRED_IDS = ("chr_0002_endminm",)
# 解析结果（上游 kind）-> API 契约的 kind；档案卡与 /api/wiki/search 共用。
RESULT_KINDS = {"operator": "character", "weapon": "weapon", "equip_set": "equipSuit"}
MAX_READINGS = 32  # 每个词的异读组合上限


def load_aliases(path: Path | None = None) -> dict[str, Any]:
    """读取昵称表；缺失或损坏时返回空表，检索退化为只用索引里的名字。"""
    try:
        payload = json.loads((path or ALIASES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def to_pinyin(text: str) -> set[str]:
    """一个词的全部无声调读法，多音字（缪 miao/miu）也能命中。"""
    if not pinyin or not _has_cjk(text):
        return set()
    readings = {""}
    for options in pinyin(text, style=Style.NORMAL, heteronym=True):
        readings = {r + o for r in readings for o in dict.fromkeys(options)}
        if len(readings) > MAX_READINGS:
            readings = set(sorted(readings)[:MAX_READINGS])
    return readings


def normalize(text: str) -> str:
    """NFKC + 小写，并去掉空白与各种中英标点，使 "J.E.T." 与 "JET" 等价。"""
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[\s·・\-_.:：,，'\"“”‘’()（）]", "", text)


@dataclass
class Result:
    # "operator" | "weapon" | "equip_set" | "no_signature" | "candidates"
    kind: str = ""
    id: str = ""
    owner: str = ""  # 查询专武时，武器所属的干员 id
    note: str = ""  # 武器：为何选中它；套装：被问到的那件装备
    candidates: list[str] = field(default_factory=list)


class Resolver:
    """把玩家输入解析成索引里的条目；索引与昵称表都是只读的普通字典。"""

    def __init__(self, index: dict, aliases: dict) -> None:
        self.index = index
        self.keys: dict[str, tuple[str, str]] = {}  # 归一化键 -> (kind, id)
        self.pinyin: dict[str, set[tuple[str, str]]] = {}  # 中文键的读音 -> 目标
        self.labels: dict[tuple[str, str], str] = {}
        name_to_op: dict[str, str] = {}
        for cid in sorted(index["operators"], key=lambda c: (c not in PREFERRED_IDS, c)):
            name_to_op.setdefault(index["operators"][cid]["name"], cid)
        for name, cid in name_to_op.items():
            op = index["operators"][cid]
            self.labels[("operator", cid)] = name
            extra = aliases.get("operators", {}).get(name, {}).get("aliases", [])
            for key in (name, op["eng"], *extra):
                self._add(key, ("operator", cid))
        name_to_wp: dict[str, str] = {}
        for wid, weapon in index["weapons"].items():
            name_to_wp.setdefault(weapon["name"], wid)
        for name, wid in name_to_wp.items():
            weapon = index["weapons"][wid]
            self.labels[("weapon", wid)] = name
            for key in (name, weapon["eng"], *aliases.get("weapons", {}).get(name, [])):
                self._add(key, ("weapon", wid))
        # 单件装备的名字也能打开它所在的套装卡。
        self.pieces: dict[str, str] = {}  # 归一化件名 -> 显示名
        for sid, equip_set in (index.get("equip_sets") or {}).items():
            self.labels[("equip_set", sid)] = equip_set["name"]
            for key in (
                equip_set["name"],
                *aliases.get("equip_sets", {}).get(equip_set["name"], []),
            ):
                self._add(key, ("equip_set", sid))
            for piece in equip_set.get("pieces") or []:
                self._add(piece["name"], ("equip_set", sid))
                self.pieces.setdefault(normalize(piece["name"]), piece["name"])
        self.alias_cfg = aliases.get("operators", {})
        self.weapon_by_name = name_to_wp

    def _add(self, key: str, target: tuple[str, str]) -> None:
        key = normalize(key)
        if len(key) >= 1 and key not in self.keys:
            self.keys[key] = target
        if len(key) >= 2:
            for reading in to_pinyin(key):
                self.pinyin.setdefault(reading, set()).add(target)

    def _find(self, query: str, kinds: tuple[str, ...]) -> Result | None:
        pool = {k: v for k, v in self.keys.items() if v[0] in kinds}
        if query in pool:
            kind, entry_id = pool[query]
            return Result(kind=kind, id=entry_id)
        if len(query) >= 2 and (readings := to_pinyin(query)):
            targets = {
                t for r in readings for t in self.pinyin.get(r, set()) if t[0] in kinds
            }
            if len(targets) == 1:
                kind, entry_id = targets.pop()
                return Result(kind=kind, id=entry_id)
        if len(query) >= MIN_PREFIX:
            targets = {v for k, v in pool.items() if k.startswith(query)}
            if len(targets) == 1:
                kind, entry_id = targets.pop()
                return Result(kind=kind, id=entry_id)
            if 1 < len(targets) <= MAX_CANDIDATES:
                return Result(
                    kind="candidates",
                    candidates=sorted(self.labels[t] for t in targets),
                )
            close = difflib.get_close_matches(query, pool.keys(), n=3, cutoff=FUZZY_CUTOFF)
            targets = {pool[k] for k in close}
            if len(targets) == 1:
                kind, entry_id = targets.pop()
                return Result(kind=kind, id=entry_id)
        return None

    def resolve(self, raw: str) -> Result | None:
        query = normalize(raw)
        if not query:
            return None
        for suffix in SIGNATURE_SUFFIXES:
            if query.endswith(suffix) and len(query) > len(suffix):
                found = self._find(query[: -len(suffix)], ("operator",))
                if not found or found.kind != "operator":
                    return found if found and found.kind == "candidates" else None
                op = self.index["operators"][found.id]
                cfg = self.alias_cfg.get(op["name"], {})
                wid = op.get("signature_weapon") or self.weapon_by_name.get(
                    cfg.get("signature_weapon") or ""
                )
                if wid:
                    return Result(kind="weapon", id=wid, owner=found.id)
                rec = self.weapon_by_name.get(cfg.get("recommended_weapon") or "")
                if rec:
                    return Result(
                        kind="weapon", id=rec, owner=found.id, note="（非专武，推荐武器）"
                    )
                return Result(kind="no_signature", id=found.id)
        found = self._find(query, ("operator", "weapon", "equip_set"))
        if found is None:
            for suffix in BUILD_SUFFIXES:
                if query.endswith(suffix) and len(query) > len(suffix):
                    owner = self._find(query[: -len(suffix)], ("operator",))
                    return owner if owner and owner.kind in ("operator", "candidates") else None
        elif found.kind == "equip_set" and self.keys.get(query) == ("equip_set", found.id):
            found.note = self.pieces.get(query, "")
        return found
