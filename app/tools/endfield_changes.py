"""索引版本差异与数据体检：纯函数，只读 index.json。

移植自 Priestess-bot 的 plugins/endfield_wiki/changes.py（MIT License，
Copyright (c) 2026 Billtranscend）。上游用于群通知与管理员告警，本项目用于
/api/wiki/sync 返回的 counts 与 problems：拿不到或没填上的数值在这里变成可读
提示，而不是让前端渲染出空白。

本模块不做存储、不发通知，也不抛异常：结构缺失一律按"空"处理。
"""

from __future__ import annotations

import re

__all__ = ["LIST_LIMIT", "added", "names", "problems"]

LIST_LIMIT = 12  # 通知中每行显示的名字数量

# 索引里空目录的说明；顺序与索引分类一致。
CATEGORY_LABELS = {
    "operators": "干员",
    "weapons": "武器",
    "equip_sets": "套装",
    "dungeons": "关卡",
    "enemies": "敌人",
}


def _entries(index: dict, key: str) -> dict:
    value = index.get(key)
    return value if isinstance(value, dict) else {}


def _rows(index: dict, key: str) -> list:
    value = index.get(key)
    return value if isinstance(value, list) else []


def _size(index: dict, key: str) -> int:
    """分类的条目数；字典与列表两种布局都支持，缺失时为 0。"""
    value = index.get(key)
    return len(value) if isinstance(value, (dict, list)) else 0


def names(index: dict) -> dict[str, list[str]]:
    """分类 -> 按索引自身顺序排列的名字。"""
    endgame = index.get("endgame") or {}
    monuments = [
        f'{series.get("name", "")}（{"、".join(group.get("name", "") for group in series.get("groups", []))}）'
        for series in _rows(endgame, "monument")
    ]
    return {
        "干员": [op.get("name", "") for op in _entries(index, "operators").values()],
        "武器": [weapon.get("name", "") for weapon in _entries(index, "weapons").values()],
        "套装": [
            equip_set.get("name", "")
            for equip_set in _entries(index, "equip_sets").values()
        ],
        "战争回响": [
            group.get("name", "")
            for group in (_entries(endgame, "tower") or {}).values()
        ],
        "影拓丰碑": monuments,
        "关卡": [row.get("name", "") for row in _rows(index, "dungeons")],
        "敌人": [row.get("name", "") for row in _rows(index, "enemies")],
    }


def added(old: dict, new: dict) -> dict[str, list[str]]:
    """新索引里多出来的名字；丰碑增加一层关卡也算新增，连同其全部关卡一起列出。"""
    before, after = names(old), names(new)
    return {
        kind: [
            name for name in after[kind] if name and name not in set(before.get(kind, ()))
        ]
        for kind in after
    }


def _joined(items: list[str]) -> str:
    shown = "、".join(items[:LIST_LIMIT])
    return shown if len(items) <= LIST_LIMIT else f"{shown} 等 {len(items)} 个"


def notice_lines(new_names: dict[str, list[str]]) -> list[str]:
    """变更通知正文：每个有新内容的分类一行，再加上怎么查。"""
    lines = [f"新增{kind}：{_joined(items)}" for kind, items in new_names.items() if items]
    if not lines:
        return ["本次没有新增内容，已有资料的数值和文本已同步更新"]
    examples = [
        f"/{new_names[kind][0]}"
        for kind in ("干员", "武器", "套装")
        if new_names.get(kind)
    ]
    if examples:
        lines.append(f"现在就可以查：发送 /名称 查看资料卡，例如 {'、'.join(examples)}")
    stage = next(
        (
            new_names[kind][0].split("（")[0]
            for kind in ("战争回响", "影拓丰碑")
            if new_names.get(kind)
        ),
        "",
    )
    if stage:
        lines.append(f"关卡发 /攻略 {stage} 看机制、敌人与阵容，/敌人 {stage} 只看敌人属性")
    return lines


def _plain(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()


def problems(index: dict) -> list[str]:
    """游戏数据用了本代码还没读的写法时会留下的痕迹：卡片上会是空白或占位符。"""
    found: list[str] = []
    for kind, label in CATEGORY_LABELS.items():
        if not _size(index, kind):
            found.append(f"索引里没有任何{label}")
    for op in _entries(index, "operators").values():
        who = f'干员「{op.get("name", "?")}」'
        if not op.get("skills"):
            found.append(f"{who}没有任何技能")
        for skill in op.get("skills", []):
            texts = [skill.get("desc", "")] + [
                form.get("desc", "") for form in skill.get("forms", [])
            ]
            if not any(_plain(t) for t in texts):
                found.append(
                    f'{who}的{skill.get("type", "技能")}「{skill.get("name", "?")}」没有说明'
                )
            elif any("{" in _plain(t) or "?" in _plain(t) for t in texts):
                found.append(
                    f'{who}的{skill.get("type", "技能")}「{skill.get("name", "?")}」有没填上的数值'
                )
        for label, rows in (("天赋", op.get("talents", [])), ("潜能", op.get("potentials", []))):
            for row in rows:
                if not _plain(row.get("desc", "")):
                    found.append(f'{who}的{label}「{row.get("name", "?")}」没有说明')
                elif "{" in _plain(row["desc"]) or "?" in _plain(row["desc"]):
                    found.append(f'{who}的{label}「{row.get("name", "?")}」有没填上的数值')
    for weapon in _entries(index, "weapons").values():
        for skill in weapon.get("skills", []):
            levels = skill.get("levels", [])
            if not levels or not all(_plain(level) for level in levels):
                found.append(
                    f'武器「{weapon.get("name", "?")}」的技能「{skill.get("name", "?")}」没有说明'
                )
            elif any("{" in _plain(level) or "?" in _plain(level) for level in levels):
                found.append(
                    f'武器「{weapon.get("name", "?")}」的技能「{skill.get("name", "?")}」有没填上的数值'
                )
    return list(dict.fromkeys(found))  # 两条「管理员」条目共用同一批文本
