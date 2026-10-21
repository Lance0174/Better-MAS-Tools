"""把索引整理成前端通用渲染所需的契约结构：检索行与资料卡。

前端只做通用渲染（sections / fields / table），所以资料的分层、字段名与缺值处理
都在这里完成；本模块是纯转换，不读写存储、不发请求。

* 索引里的文本带游戏富文本转来的 HTML（<span class="...">、<br>），契约字段是纯
  字符串，因此这里统一去标签、还原换行，避免前端把标签当正文显示。
* 任何取不到的数值都用空字符串，不抛异常；数组字段缺失时返回空列表。
* 检索只覆盖索引里已有的名字与昵称表里的别名，匹配顺序为：精确、唯一前缀、
  同音字（需 pypinyin，缺失时自动跳过）、difflib 近似纠错。

昵称表与匹配规则来自 Priestess-bot 的 plugins/endfield_wiki/lookup.py 与
aliases.json（MIT License，Copyright (c) 2026 Billtranscend），见 NOTICE.md。
"""

from __future__ import annotations

import difflib
import re
from typing import Any

from app.tools.akedata_client import (
    SKILL_LEVELS,
    char_icon_url,
    enemy_icon_url,
    equip_icon_url,
    weapon_icon_url,
)
from app.tools.endfield_lookup import normalize, to_pinyin

__all__ = [
    "ENTRY_KINDS",
    "FUZZY_CUTOFF",
    "SEARCH_LIMIT_MAX",
    "SEARCH_LIMIT_MIN",
    "entry",
    "plain",
    "search",
]

ENTRY_KINDS = ("character", "weapon", "equipSuit", "dungeon", "enemy")
SEARCH_LIMIT_MIN = 1
SEARCH_LIMIT_MAX = 50
FUZZY_CUTOFF = 0.6  # 检索放宽到 0.6：这里是候选列表，不是自动选中
VALUE_LIMIT = 20000  # 单个字段的字符上限，避免异常数据撑爆响应


def plain(value: Any) -> str:
    """去掉索引里的 HTML 标签并还原换行；非字符串一律转成空字符串。"""
    if not isinstance(value, str):
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value)
    text = re.sub(r"<[^>]+>", "", text)
    return text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")[
        :VALUE_LIMIT
    ].strip()


def _text(value: Any) -> str:
    """标量转字符串；None 与数字 0 的分支在调用处判断。"""
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return f"{value:g}"
    return plain(value)


def _rows(index: dict, key: str) -> list:
    value = index.get(key)
    return value if isinstance(value, list) else []


def _catalog_rows(index: dict, aliases: dict) -> list[dict]:
    """检索目录：每行带多种可匹配的键，以及契约需要的最小展示信息。"""
    rows: list[dict] = []

    def add(kind: str, entry_id: str, name: str, subtitle: str, icon: str, keys: list):
        if not name:
            return
        normalized = [normalize(key) for key in [name, *keys] if key]
        rows.append(
            {
                "kind": kind,
                "id": entry_id,
                "name": name,
                "subtitle": subtitle,
                "icon": icon,
                "keys": [k for k in dict.fromkeys(normalized) if k],
            }
        )

    operator_aliases = aliases.get("operators", {})
    for cid, op in (index.get("operators") or {}).items():
        cfg = operator_aliases.get(op.get("name", ""), {})
        add(
            "character",
            cid,
            op.get("name", ""),
            " · ".join(
                part
                for part in (
                    f'{op.get("rarity", 0)}★' if op.get("rarity") else "",
                    op.get("profession", ""),
                    op.get("element", ""),
                )
                if part
            ),
            char_icon_url(cid),
            [op.get("eng", ""), *(cfg.get("aliases") or [])],
        )
    weapon_aliases = aliases.get("weapons", {})
    for wid, weapon in (index.get("weapons") or {}).items():
        add(
            "weapon",
            wid,
            weapon.get("name", ""),
            " · ".join(
                part
                for part in (
                    f'{weapon.get("rarity", 0)}★' if weapon.get("rarity") else "",
                    weapon.get("type", ""),
                    f'专武 · {weapon["owner"]}' if weapon.get("owner") else "",
                )
                if part
            ),
            weapon_icon_url(weapon.get("icon") or wid),
            [weapon.get("eng", ""), *(weapon_aliases.get(weapon.get("name", "")) or [])],
        )
    set_aliases = aliases.get("equip_sets", {})
    for sid, equip_set in (index.get("equip_sets") or {}).items():
        pieces = equip_set.get("pieces") or []
        add(
            "equipSuit",
            sid,
            equip_set.get("name", ""),
            " · ".join(
                part
                for part in (
                    f'{equip_set.get("rarity", 0)}★' if equip_set.get("rarity") else "",
                    f'{equip_set.get("count", 3)} 件套',
                    equip_set.get("domain", ""),
                )
                if part
            ),
            equip_icon_url(pieces[0].get("icon", "") if pieces else ""),
            [
                *(set_aliases.get(equip_set.get("name", "")) or []),
                *(piece.get("name", "") for piece in pieces),
            ],
        )
    for row in _rows(index, "dungeons"):
        add(
            "dungeon",
            row.get("id", ""),
            row.get("name", ""),
            " · ".join(
                part
                for part in (
                    row.get("category", ""),
                    row.get("level_desc", ""),
                    f'推荐 {row["recommend_lv"]}' if row.get("recommend_lv") else "",
                )
                if part
            ),
            "",
            [row.get("base_name", "")],
        )
    for row in _rows(index, "enemies"):
        add(
            "enemy",
            row.get("id", ""),
            row.get("name", ""),
            "领袖敌人" if row.get("leader") else "敌人",
            enemy_icon_url(row.get("id", "")),
            [row.get("template", "")],
        )
    return rows


def _rank(rows: list[dict], query: str, limit: int) -> list[dict]:
    """精确 -> 唯一前缀 -> 同音字 -> 近似，四级依次补齐，按 (kind, id) 去重。"""
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def take(items) -> None:
        for row in items:
            key = (row["kind"], row["id"])
            if key not in seen and len(found) < limit:
                seen.add(key)
                found.append(row)

    take(sorted((r for r in rows if query in r["keys"]), key=lambda r: len(r["name"])))
    take(
        sorted(
            (r for r in rows if any(k.startswith(query) for k in r["keys"])),
            key=lambda r: (len(r["name"]), r["name"]),
        )
    )
    cache: dict[str, set[str]] = {}

    def readings(text: str) -> set[str]:
        # 同一次检索里每个键只算一次；未安装 pypinyin 时 to_pinyin 直接返回空集。
        if text not in cache:
            cache[text] = to_pinyin(text)
        return cache[text]

    if len(query) >= 2 and (wanted := readings(query)):
        take(
            sorted(
                (r for r in rows if any(readings(key) & wanted for key in r["keys"])),
                key=lambda r: (len(r["name"]), r["name"]),
            )
        )
    if len(found) < limit:
        by_name = {row["name"]: row for row in rows if row["name"]}
        close = difflib.get_close_matches(
            query, list(by_name), n=limit * 2, cutoff=FUZZY_CUTOFF
        )
        take(sorted((by_name[name] for name in close), key=lambda r: r["name"]))
    return found[:limit]


def search(index: dict, aliases: dict, query: str, limit: int) -> list[dict]:
    """检索资料条目；关键词为空时返回空列表，绝不抛出。"""
    cleaned = normalize(query)
    if not cleaned:
        return []
    bounded = min(max(int(limit), SEARCH_LIMIT_MIN), SEARCH_LIMIT_MAX)
    return _rank(_catalog_rows(index, aliases), cleaned, bounded)


def _fields(pairs) -> list[dict]:
    """(label, value) 对 -> 契约字段；值为空时保留字段，前端可自行隐藏。"""
    return [{"label": str(label), "value": _text(value)} for label, value in pairs]


def _section(title: str, fields: list[dict], table: dict | None = None) -> dict:
    section = {"title": title, "fields": fields}
    if table:
        section["table"] = table
    return section


def _skill_table(skill: dict) -> dict | None:
    rows = skill.get("table") or []
    if not rows:
        return None
    return {
        "columns": ["项目", *SKILL_LEVELS],
        "rows": [
            [_text(row.get("label")), *[_text(v) for v in row.get("values") or []]]
            for row in rows
        ],
    }


def _operator(index: dict, entry_id: str) -> dict | None:
    op = (index.get("operators") or {}).get(entry_id)
    if not op:
        return None
    name = op.get("name", "")
    tags = [tag for tag in (op.get("profession", ""), op.get("element", "")) if tag]
    if op.get("rarity"):
        tags.append(f'{op["rarity"]}★')
    sections = [
        _section(
            "干员信息",
            _fields(
                (
                    ("英文名", op.get("eng", "")),
                    ("职业", op.get("profession", "")),
                    ("武器类型", op.get("weapon_type", "")),
                    ("属性", op.get("element", "")),
                    ("主属性", op.get("main_attr", "")),
                    ("副属性", op.get("sub_attr", "")),
                    ("所属部门", op.get("department", "")),
                    ("专武", (index.get("weapons") or {}).get(op.get("signature_weapon") or "", {}).get("name", "")),
                )
            ),
        )
    ]
    stats = op.get("stats") or []
    if stats:
        sections.append(_section("满级属性", _fields(stats)))
    for skill in op.get("skills") or []:
        fields = _fields(
            (
                ("类型", skill.get("type", "")),
                ("说明", skill.get("desc", "")),
                *[
                    (f'形态 · {form.get("name", "")}', form.get("desc", ""))
                    for form in skill.get("forms") or []
                ],
            )
        )
        sections.append(
            _section(f'技能 · {skill.get("name", "")}', fields, _skill_table(skill))
        )
    if op.get("talents"):
        sections.append(
            _section(
                "天赋",
                _fields((t.get("name", ""), t.get("desc", "")) for t in op["talents"]),
            )
        )
    if op.get("potentials"):
        sections.append(
            _section(
                "潜能",
                _fields(
                    (f'{p.get("level", "")} · {p.get("name", "")}', p.get("desc", ""))
                    for p in op["potentials"]
                ),
            )
        )
    for slot in op.get("logistics") or []:
        levels = slot.get("levels") or []
        sections.append(
            _section(
                f'后勤技能 · {slot.get("name", "")}',
                _fields(
                    (
                        f'{slot.get("room", "")} · {level.get("postfix") or f"等级 {i + 1}"}',
                        " ".join(
                            part
                            for part in (level.get("desc", ""), f'（{level["unlock"]}）' if level.get("unlock") else "")
                            if part
                        ),
                    )
                    for i, level in enumerate(levels)
                ),
            )
        )
    return {
        "kind": "character",
        "id": entry_id,
        "name": name,
        "subtitle": " · ".join(tags),
        "icon": char_icon_url(entry_id),
        "tags": tags,
        "sections": sections,
    }


def _weapon(index: dict, entry_id: str) -> dict | None:
    weapon = (index.get("weapons") or {}).get(entry_id)
    if not weapon:
        return None
    tags = [tag for tag in (weapon.get("type", ""),) if tag]
    if weapon.get("rarity"):
        tags.append(f'{weapon["rarity"]}★')
    sections = [
        _section(
            "武器信息",
            _fields(
                (
                    ("英文名", weapon.get("eng", "")),
                    ("类型", weapon.get("type", "")),
                    ("攻击力上限", weapon.get("max_atk", "")),
                    ("等级上限", weapon.get("max_lv", "")),
                    ("专武持有者", weapon.get("owner", "")),
                    ("描述", weapon.get("deco", "")),
                )
            ),
        )
    ]
    for skill in weapon.get("skills") or []:
        sections.append(
            _section(
                f'武器技能 · {skill.get("name", "")}',
                _fields(
                    (f"精炼 {i + 1}", level)
                    for i, level in enumerate(skill.get("levels") or [])
                ),
            )
        )
    return {
        "kind": "weapon",
        "id": entry_id,
        "name": weapon.get("name", ""),
        "subtitle": " · ".join(tags),
        "icon": weapon_icon_url(weapon.get("icon") or entry_id),
        "tags": tags,
        "sections": sections,
    }


def _equip_suit(index: dict, entry_id: str) -> dict | None:
    equip_set = (index.get("equip_sets") or {}).get(entry_id)
    if not equip_set:
        return None
    pieces = equip_set.get("pieces") or []
    tags = [tag for tag in (equip_set.get("domain", ""),) if tag]
    if equip_set.get("rarity"):
        tags.append(f'{equip_set["rarity"]}★')
    table = None
    if pieces:
        table = {
            "columns": ["名称", "部位", "星级", "需求等级", "防御", "属性"],
            "rows": [
                [
                    _text(piece.get("name", "")),
                    _text(piece.get("part", "")),
                    _text(piece.get("rarity", "")),
                    _text(piece.get("level", "")),
                    _text(piece.get("defense", "")),
                    "、".join(
                        " ".join(
                            part
                            for part in (
                                attr.get("name", ""),
                                attr.get("base", ""),
                                f'→ {attr["max"]}' if attr.get("max") else "",
                            )
                            if part
                        )
                        for attr in piece.get("attrs") or []
                    ),
                ]
                for piece in pieces
            ],
        }
    sections = [
        _section(
            "套装信息",
            _fields(
                (
                    ("件数", equip_set.get("count", "")),
                    ("星级", equip_set.get("rarity", "")),
                    ("需求等级", equip_set.get("level", "")),
                    ("区域", equip_set.get("domain", "")),
                    ("套装效果", equip_set.get("effect", "")),
                )
            ),
            table,
        )
    ]
    return {
        "kind": "equipSuit",
        "id": entry_id,
        "name": equip_set.get("name", ""),
        "subtitle": " · ".join(tags),
        "icon": equip_icon_url(pieces[0].get("icon", "") if pieces else ""),
        "tags": tags,
        "sections": sections,
    }


def _dungeon(index: dict, entry_id: str) -> dict | None:
    row = next(
        (item for item in _rows(index, "dungeons") if item.get("id") == entry_id), None
    )
    if not row:
        return None
    tags = [tag for tag in (row.get("category", ""),) if tag]
    levels = row.get("levels") or []
    sections = [
        _section(
            "关卡信息",
            _fields(
                (
                    ("类别", row.get("category", "")),
                    ("层数", row.get("level_desc", "")),
                    ("推荐等级", row.get("recommend_lv", "")),
                    ("敌人等级", "、".join(_text(v) for v in levels)),
                    ("敌人数量", row.get("enemy_count", "")),
                    ("场景", row.get("scene", "")),
                    ("说明", row.get("feature", "")),
                )
            ),
        )
    ]
    return {
        "kind": "dungeon",
        "id": entry_id,
        "name": row.get("name", ""),
        "subtitle": " · ".join(tags),
        "icon": "",
        "tags": tags,
        "sections": sections,
    }


def _enemy(index: dict, entry_id: str) -> dict | None:
    row = next(
        (item for item in _rows(index, "enemies") if item.get("id") == entry_id), None
    )
    if not row:
        return None
    stats = row.get("stats") or {}
    tags = ["领袖敌人"] if row.get("leader") else ["敌人"]
    sections = [
        _section(
            "敌人信息",
            _fields(
                (
                    ("类型", tags[0]),
                    ("模板", row.get("template", "")),
                    ("说明", row.get("desc", "")),
                )
            ),
        )
    ]
    if stats:
        sections.append(
            _section(
                "默认属性",
                _fields(
                    (
                        ("生命值", stats.get("hp", "")),
                        ("攻击力", stats.get("atk", "")),
                        ("防御力", stats.get("def", "")),
                        ("失衡值上限", stats.get("poise", "")),
                    )
                ),
            )
        )
    if stats.get("res"):
        sections.append(
            _section(
                "抗性",
                [],
                {
                    "columns": ["属性", "抗性"],
                    "rows": [
                        [_text(label), _text(value)] for label, value in stats["res"]
                    ],
                },
            )
        )
    if row.get("traits"):
        sections.append(
            _section(
                "特性",
                _fields(
                    (f"特性 {i + 1}", trait)
                    for i, trait in enumerate(row.get("traits") or [])
                ),
            )
        )
    return {
        "kind": "enemy",
        "id": entry_id,
        "name": row.get("name", ""),
        "subtitle": tags[0],
        "icon": enemy_icon_url(entry_id),
        "tags": tags,
        "sections": sections,
    }


_BUILDERS = {
    "character": _operator,
    "weapon": _weapon,
    "equipSuit": _equip_suit,
    "dungeon": _dungeon,
    "enemy": _enemy,
}


def entry(index: dict, kind: str, entry_id: str) -> dict | None:
    """资料卡；kind 或 id 对不上时返回 None（由接口转成可读错误）。"""
    builder = _BUILDERS.get(kind)
    if builder is None or not entry_id:
        return None
    return builder(index, entry_id)
