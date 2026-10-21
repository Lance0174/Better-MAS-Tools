"""AKEData（https://www.akedata.wiki/）同步客户端与紧凑索引构建。

移植自 Priestess-bot 的 plugins/endfield_wiki/data.py（MIT License，
Copyright (c) 2026 Billtranscend），去掉 nonebot 依赖，改用本项目的网络层
（app/services/network.py，显式 trust_env=False），并拆出 dungeons / enemies
两张扁平表供 /api/wiki 检索。来源与许可见 NOTICE.md。

站点在 data.akedata.wiki 上发布解包后的游戏表：先取几 KB 的 manifest，版本变化时
才下载需要的表，再压缩成一份索引。关卡敌人还需要表目录旁的场景文件：spawner 配置
说明关卡会刷出哪些敌人变体、它们出生时带什么 buff，buff 文件则记录这些 buff 对属性
做了什么。

本模块只做平台协议与纯转换：不读写存储、不编排、不发通知，网络结果由调用方决定
是否落盘。
"""

from __future__ import annotations

import ast
import asyncio
import json
import operator
import re
import shutil
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.services.network import network

__all__ = [
    "AkedataError",
    "INDEX_SCHEMA",
    "TABLES",
    "build_calendar",
    "build_dungeons",
    "build_endgame",
    "build_enemies",
    "build_index",
    "build_leaders",
    "char_icon_url",
    "download_tables",
    "enemy_icon_url",
    "equip_icon_url",
    "fetch_manifest",
    "fill_placeholders",
    "http_client",
    "index_counts",
    "latest_version",
    "logistics_icon_url",
    "remove_tree",
    "rich_to_html",
    "stage_cover_url",
    "stage_stats",
    "weapon_icon_url",
]

DATA_BASE = "https://data.akedata.wiki"
MANIFEST_URL = f"{DATA_BASE}/manifest.json"
MAPS_URL = "https://www.akedata.wiki/public/CH/maps.json"
ASSET_INDEX_URL = f"{DATA_BASE}/asset-sync-index.json"  # public/Json 下全部文件清单
JSON_BASE = f"{DATA_BASE}/public/Json"
STAGE_FETCHES = 4  # 关卡小文件的并发下载数
SAFE_PATH = re.compile(r"^(?:SpawnerConfig/\w[\w.-]*|BuffData)/\w[\w.-]*\.json$")
IMAGE_BASE = f"{DATA_BASE}/public/images/assets/beyond/dynamicassets/gameplay/ui/sprites"
USER_AGENT = "Better-MAS-Tools/1.0 (independent community toolkit; data from AKEData)"
TABLES = (
    "I18nTextTable_CN",
    "CharacterTable",
    "CharGrowthTable",
    "CharacterPotentialTable",
    "PotentialTalentEffectTable",
    "SkillPatchTable",
    "CharWpnRecommendTable",
    "WeaponBasicTable",
    "WeaponUpgradeTemplateTable",
    "ItemTable",
    "EquipTable",
    "EquipSuitTable",
    "DungeonTable",
    "DungeonSeriesTable",
    "SeasonTowerTable",
    "SeasonTowerGameGroupTable",
    "SeasonTowerDungeonTable",
    "TimeRangeTable",
    "EnemyTemplateDisplayInfoTable",
    "EnemyTable",
    "EnemyAttributeTemplateTable",
    "EnemyAbilityDescTable",
    "SpaceshipCharSkillTable",
    "SpaceshipSkillTable",
    "ActivityTable",
    "GachaCharPoolTable",
    "GachaWeaponPoolTable",
    "GachaCharPoolTypeTable",
    "GachaWeaponPoolTypeTable",
    "RewardTable",
    "BattlePassTaskTable",
    "BattlePassConditionTable",
    "ActivityWeeklyTaskTable",
    "ActivityWeeklyTaskMileStoneTable",
)
# 索引布局变化时 +1 以强制重建（上游 INDEX_SCHEMA 到 19：18 为领袖敌人，19 为后勤技能）。
# 本项目另有差异：+1 起为 BMT 版式，追加 dungeons / enemies 两张扁平表。
INDEX_SCHEMA = 20
# 敌人抗性属性 id（AttributeShowConfigTable），按游戏内展示顺序。
ENEMY_RESISTANCES = (
    (94, "物理"),
    (98, "灼热"),
    (97, "电磁"),
    (96, "寒冷"),
    (95, "自然"),
    (99, "超域"),
)
TOWER_DIFFICULTIES = {"1": "普通", "2": "困难", "3": "残酷"}
SKILL_TYPES = {0: "普通攻击", 1: "战技", 3: "连携技", 2: "终结技"}
SKILL_ORDER = (0, 1, 3, 2)
SKILL_LEVELS = ("Lv9", "M1", "M2", "M3")  # 技能十二级中的最后四级，出现在数值表里
COST_LABELS = {1: "技力消耗", 2: "所需终结技能量"}  # costValue 的含义由技能组类型决定
BASE_ATTRS = (("1", "生命值"), ("2", "攻击力"))  # 终末地基础防御恒为 0，防御来自装备
STAT_LEVEL = 90  # 当前玩家等级上限；表里还有更高等级
EQUIP_PARTS = {0: "护甲", 1: "护手", 2: "配件"}
# 生命值、攻击力、防御、四项能力与源石技艺强度是纯数值，其余按比例展示。
EQUIP_FLAT_ATTRS = {1, 2, 3, 39, 40, 41, 42, 87}
# 关卡类别（DungeonTable.dungeonCategory）-> 展示名；未列出的类别原样展示。
DUNGEON_KINDS = {
    "dungeon_highdifficulty": "高难关卡",
    "dungeon_bossrush": "领袖挑战",
    "dungeon_main": "主线",
    "dungeon_activity": "活动关卡",
    "dungeon_weekly": "周期关卡",
}


class AkedataError(RuntimeError):
    """同步失败的可读原因。

    只携带端点路径与状态码一类的字段，绝不附带上游响应体、URL 查询参数或凭据。
    """


def _endpoint(url: str) -> str:
    """日志与错误信息里只保留路径，避免把查询参数写进文案。"""
    return url.split("?", 1)[0]


def http_client(
    proxy: str | None = None, transport: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    """AKEData 客户端：沿用本进程的代理设置，不读取环境代理变量。"""
    options: dict[str, Any] = {
        "proxy": network.proxy if proxy is None else proxy,
        "trust_env": False,
        "headers": {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
        "timeout": httpx.Timeout(120.0, connect=20.0),
        "follow_redirects": True,
    }
    if transport is not None:
        # 测试注入假传输层；生产路径不传。
        options["transport"] = transport
    return network.client(**options)


async def _get_json(client: httpx.AsyncClient, url: str, headers: dict | None = None):
    try:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise AkedataError(
            f"数据源返回 HTTP {error.response.status_code}（{_endpoint(url)}）"
        ) from None
    except httpx.HTTPError as error:
        raise AkedataError(
            f"数据源请求失败（{_endpoint(url)}）：{type(error).__name__}"
        ) from None
    try:
        return response.json()
    except ValueError:
        raise AkedataError(f"数据源返回的不是有效 JSON（{_endpoint(url)}）") from None


async def fetch_manifest(client: httpx.AsyncClient) -> dict[str, Any]:
    """站点当前的版本列表。

    每次都完整读取并绕开缓存：它只有几 KB，而把它的 latest 与索引里的版本对比，
    是唯一不会被过期 ETag 或 CDN 副本欺骗的检查。
    """
    payload = await _get_json(
        client, MANIFEST_URL, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"}
    )
    if not isinstance(payload, dict) or not payload.get("versions"):
        raise AkedataError("数据源版本清单格式不正确")
    return payload


def latest_version(manifest: dict[str, Any]) -> dict[str, Any]:
    """manifest.latest 指向的那个版本；缺失时退回列表首项。"""
    versions = manifest.get("versions") or []
    for entry in versions:
        if entry.get("id") == manifest.get("latest"):
            return entry
    if not versions:
        raise AkedataError("数据源版本清单里没有版本条目")
    return versions[0]


MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024  # 单个数据文件的体积上限（体积最大的是敌人表）


def _write_limited(path: Path, content: bytes, *, label: str) -> None:
    """校验后落盘：数据源异常时不能把超大或空内容静默写进缓存。

    体积上限只是兜底而不是内容校验：上游若返回错误页面，JSON 解析会在后面失败，
    这里拦的是"响应被替换成几百 MB 二进制"这类情况，避免写满磁盘。
    """

    if not content:
        raise AkedataError(f"{label} 内容为空")
    if len(content) > MAX_DOWNLOAD_BYTES:
        raise AkedataError(
            f"{label} 体积异常（{len(content) // (1024 * 1024)} MB），已中止下载"
        )
    path.write_bytes(content)


async def download_tables(
    client: httpx.AsyncClient, table_path: str, target: Path
) -> None:
    """下载索引需要的全部表，以及关卡敌人用到的场景与 buff 文件。"""
    target.mkdir(parents=True, exist_ok=True)
    for name in TABLES:
        url = f"{DATA_BASE}/{table_path}/{name}.json"
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise AkedataError(
                f"数据表 {name} 返回 HTTP {error.response.status_code}"
            ) from None
        except httpx.HTTPError as error:
            raise AkedataError(f"数据表 {name} 下载失败：{type(error).__name__}") from None
        _write_limited(target / f"{name}.json", response.content, label=f"数据表 {name}")
    response = await client.get(MAPS_URL)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        raise AkedataError(f"映射表返回 HTTP {error.response.status_code}") from None
    _write_limited(target / "maps.json", response.content, label="映射表")
    await download_stage_data(client, target)


def endgame_stage_ids(series: dict, tower_groups: dict) -> list[str]:
    """终局玩法的全部关卡 id：战争回响的层 + 高难系列包含的关卡。"""
    stage_ids = [
        star["gameId"]
        for group in tower_groups.values()
        for star in group.get("stars", {}).values()
        if star.get("gameId")
    ]
    for row in series.values():
        if row.get("gameCategory") == "dungeon_highdifficulty":
            stage_ids += row.get("includeDungeonIds", [])
    return stage_ids


async def download_stage_data(client: httpx.AsyncClient, target: Path) -> None:
    """终局场景的 spawner 配置，以及其中敌人出生时带的全部 buff。"""

    def table(name: str) -> dict:
        return json.loads((target / f"{name}.json").read_text("utf-8"))

    dungeons, enemies = table("DungeonTable"), table("EnemyTable")
    stage_ids = [
        s
        for s in endgame_stage_ids(
            table("DungeonSeriesTable"), table("SeasonTowerGameGroupTable")
        )
        if s in dungeons
    ]
    scenes = {dungeons[s].get("sceneId") for s in stage_ids}
    payload = await _get_json(client, ASSET_INDEX_URL)
    try:
        files = payload["datasets"]["json"]["files"]
    except (KeyError, TypeError):
        raise AkedataError("资源清单格式不正确") from None
    limit = asyncio.Semaphore(STAGE_FETCHES)

    async def fetch(path: str) -> dict:
        async with limit:
            response = await client.get(f"{JSON_BASE}/{quote(path)}")
            response.raise_for_status()
        out = target / path
        out.parent.mkdir(parents=True, exist_ok=True)
        _write_limited(out, response.content, label=f"关卡数据 {path}")
        return response.json()

    paths = [
        p
        for p in files
        if SAFE_PATH.match(p)
        and p.startswith("SpawnerConfig/")
        and p.split("/")[1] in scenes
    ]
    configs = await asyncio.gather(*(fetch(p) for p in paths))
    enemy_ids = {e for s in stage_ids for e in dungeons[s].get("enemyIds", [])}
    buff_ids = set()
    for config in configs:
        for entry in config.get("enemyLibrary") or []:
            enemy_ids.add(entry.get("enemyId"))
            buff_ids.update(b.get("buffId") for b in entry.get("bornBuffList") or [])
    for enemy_id in enemy_ids:
        buff_ids.update(enemies.get(enemy_id, {}).get("bornBuffs") or [])
    paths = [
        p
        for p in (f"BuffData/{b}.json" for b in sorted(filter(None, buff_ids)))
        if p in files and SAFE_PATH.match(p)
    ]
    await asyncio.gather(*(fetch(p) for p in paths))


# ── 文本格式化 ─────────────────────────────────────────────────────────


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _safe_eval(expr: str, values: dict[str, float]) -> float:
    """只对数字与已知变量名做 +-*/ 求值。"""

    def walk(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            return values[node.id.lower()]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -walk(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](walk(node.left), walk(node.right))
        raise ValueError("unsupported expression")

    return walk(ast.parse(expr, mode="eval"))


def _format_number(value: float, fmt: str) -> str:
    if "%" in fmt:
        decimals = len(fmt.split(".")[1].rstrip("%")) if "." in fmt else 0
        return f"{value * 100:.{decimals}f}%"
    if "." in fmt:
        return f"{value:.{len(fmt.split('.')[1])}f}"
    if "0" in fmt:
        return str(round(value))
    return f"{value:g}"


def fill_placeholders(text: str, values: dict[str, float]) -> str:
    """把 "{atk:0.0%}" 一类占位符换成数值；取不到值就留问号，由体检报告出来。"""

    def replace(match: re.Match) -> str:
        expr, _, fmt = match.group(1).partition(":")
        try:
            return _format_number(_safe_eval(expr.replace(" ", ""), values), fmt.strip())
        except (KeyError, ValueError, SyntaxError, ZeroDivisionError):
            return "?"

    return re.sub(r"\{([^{}]+)\}", replace, text)


def strip_live_values(text: str) -> str:
    """去掉显示玩家自己队伍数值的括号段，例如 智识值({floor:deck_wisd:0})。"""
    return re.sub(r"[（(][^（）()]*\{floor:[^{}]+\}[^（）()]*[）)]", "", text)


def rich_to_html(text: str) -> str:
    """把游戏富文本（<@style>..</>、<#term>..</>、换行）转为安全 HTML。"""
    out, stack, pos = [], [], 0
    for match in re.finditer(r"<([@#])([^<>]*)>|</>|<image[^>]*>", text):
        out.append(escape(text[pos : match.start()]))
        pos = match.end()
        token = match.group(0)
        if token == "</>":
            if stack:
                out.append("</span>")
                stack.pop()
        elif token.startswith("<image"):
            continue
        else:
            kind, name = match.group(1), match.group(2)
            if kind == "#":
                cls = "term"
            elif "info" in name:
                cls = "info"
            elif "vup" in name or "num" in name:
                cls = "up"
            elif "vdown" in name:
                cls = "down"
            else:
                cls = "key"
            out.append(f'<span class="{cls}">')
            stack.append(cls)
    out.append(escape(text[pos:]))
    out.extend("</span>" for _ in stack)
    return "".join(out).replace("\\n", "<br>").replace("\n", "<br>")


# ── 索引构建 ───────────────────────────────────────────────────────────


def build_index(table_dir: Path, version: dict[str, Any]) -> dict[str, Any]:
    """把下载好的游戏表压缩成一份索引；调用方负责落盘。

    这里对应 data.py 中的 build_index，逐段保留其取值口径：技能与数值表的填充、
    专武判定、套装 3 件效果、终局关卡敌人属性与抗性。
    """

    def load(name: str) -> Any:
        return json.loads((table_dir / f"{name}.json").read_text("utf-8"))

    i18n = load("I18nTextTable_CN")
    maps = load("maps")

    def text(obj: Any) -> str:
        if isinstance(obj, dict):
            return i18n.get(str(obj.get("id")), "") or obj.get("text", "") or ""
        return obj if isinstance(obj, str) else ""

    chars, growth = load("CharacterTable"), load("CharGrowthTable")
    ship_chars, ship_skills = load("SpaceshipCharSkillTable"), load("SpaceshipSkillTable")

    def logistics(cid: str) -> list[dict]:
        """后勤技能：按槽位聚合，每个槽位带 α/β/γ 等级与解锁提示。"""
        slots: dict[str, dict] = {}
        for entry in (ship_chars.get(cid) or {}).get("skillList") or []:
            skill = ship_skills.get(entry.get("skillId"))
            if not skill:
                continue
            name = text(skill.get("talentName"))
            slot = slots.setdefault(
                name,
                {
                    "name": name,
                    "room": maps["room_type_map"].get(str(skill.get("roomType")), ""),
                    "icon": skill.get("icon", ""),
                    "levels": [],
                },
            )
            slot["levels"].append(
                {
                    "postfix": skill.get("skillNamePostfix", ""),
                    "desc": rich_to_html(text(skill.get("desc"))),
                    "unlock": text(entry.get("unlockHint")),
                }
            )
        return list(slots.values())

    potentials, effects = (
        load("CharacterPotentialTable"),
        load("PotentialTalentEffectTable"),
    )
    skills, recommend = load("SkillPatchTable"), load("CharWpnRecommendTable")
    weapons_basic, upgrades, items = (
        load("WeaponBasicTable"),
        load("WeaponUpgradeTemplateTable"),
        load("ItemTable"),
    )
    attr_names, attr_keys = maps["ATTR_MAP"], maps["ATTR_MAP_EN"]
    param_keys = maps["param_type_map"]

    def effect_values(effect: dict) -> dict[str, float]:
        values: dict[str, float] = {}
        for data in effect.get("dataList", []):
            for holder in ("attachBuff", "attachSkill"):
                for entry in data.get(holder, {}).get("blackboard", []):
                    values[entry["key"].lower()] = entry["value"]
            bb = data.get("skillBbModifier", {})
            if bb.get("bbKey"):
                values[bb["bbKey"].lower()] = bb.get("floatValue", 0.0)
            attr = data.get("attrModifier", {})
            if attr.get("attrType"):
                key = attr_keys.get(str(attr["attrType"]), "")
                if key:
                    values[key.lower()] = attr.get("attrValue", 0.0)
            param = data.get("skillParamModifier", {})
            if param.get("paramType"):
                values[param_keys.get(str(param["paramType"]), "").lower()] = param.get(
                    "paramValue", 0.0
                )
        return values

    def max_level_values(skill_ids: list[str]) -> dict[str, float]:
        values: dict[str, float] = {}
        for skill_id in skill_ids:
            bundle = skills.get(skill_id, {}).get("SkillPatchDataBundle", [])
            if bundle:
                top = bundle[-1]
                for entry in top.get("blackboard", []):
                    # 技能组里靠后的技能覆盖前面的取值，与 AKEData 站点一致。
                    values[entry["key"].lower()] = entry["value"]
                values.setdefault("cooldown", top.get("coolDown", 0.0))
                values.setdefault("costvalue", top.get("costValue", 0.0))
        return values

    def level_number(value: float) -> str:
        return f"{value:g}"

    def level_table(
        group: dict, form_names: dict[str, str], talent_effects: list[dict]
    ) -> list[dict]:
        """技能组的分级数值表。

        消耗与冷却取自技能组的首个技能；其余行是组内每个技能在游戏里都会显示的具名
        数值（subDescDataList），顺序照旧。只在某个形态生效的数值会带上形态名。
        """
        skill_ids = group.get("skillIdList", [])
        bundles = [
            bundle
            for skill_id in skill_ids
            if (bundle := skills.get(skill_id, {}).get("SkillPatchDataBundle", []))
        ]
        if not bundles:
            return []
        shown = slice(-len(SKILL_LEVELS), None)
        rows: list[dict] = []
        cost = [patch.get("costValue") or 0 for patch in bundles[0]]
        cooldown = [patch.get("coolDown") or 0 for patch in bundles[0]]
        kind = group.get("skillGroupType")
        if any(cost):
            rows.append(
                {
                    "label": COST_LABELS.get(kind, "消耗"),
                    "values": [level_number(v) for v in cost[shown]],
                }
            )
        if any(cooldown):
            if kind == 3 and len(form_names) > 1:
                # 天赋可能在某个形态下缩短连携技冷却，逐形态补上该差值。
                for form_id, form_name in form_names.items():
                    sums, seen = {2: 0.0, 4: 0.0}, set()
                    for effect in talent_effects:
                        for item in effect.get("dataList", []):
                            param = item.get("skillParamModifier") or {}
                            if (
                                param.get("paramType") not in (2, 4)
                                or param.get("modifyType") != 1
                            ):
                                continue
                            if param.get("skillId") not in skill_ids or form_id not in (
                                item.get("activeCondition") or []
                            ):
                                continue
                            sums[param["paramType"]] += param.get("paramValue") or 0.0
                            seen.add(param["paramType"])
                    shift = sums[4] if 4 in seen else sums[2] if 2 in seen else 0.0
                    rows.append(
                        {
                            "label": f"{form_name} · 冷却时间（秒）",
                            "values": [level_number(v + shift) for v in cooldown[shown]],
                        }
                    )
            else:
                rows.append(
                    {
                        "label": "冷却时间（秒）",
                        "values": [level_number(v) for v in cooldown[shown]],
                    }
                )
        stagger = (
            re.search(r"\{\s*(\w+)[^{}]*\}(?:</>)?点失衡", text(group.get("desc")))
            if kind == 0
            else None
        )
        if stagger:
            # 重击失衡值只在描述里给出（"重击会造成{poise:0}点失衡"），其分级数值取自
            # 填充该描述的技能（组内最后一个设置它的技能）。
            key = stagger.group(1).lower()
            poise = [
                next(
                    (
                        e["value"]
                        for b in reversed(bundles)
                        for e in b[level].get("blackboard", [])
                        if e["key"].lower() == key
                    ),
                    None,
                )
                for level in range(len(bundles[0]))
            ]
            if all(v is not None for v in poise):
                rows.append(
                    {
                        "label": "重击失衡值",
                        "values": [level_number(v) for v in poise[shown]],
                    }
                )
        for bundle in bundles:
            named: dict[tuple, dict] = {}
            for level, patch in enumerate(bundle):
                occurrence: dict[tuple, int] = {}
                for sub in patch.get("subDescDataList", []):
                    name = text(sub.get("name"))
                    if not name:
                        continue
                    form_id = sub.get("conditionId") or ""
                    nth = occurrence.get((form_id, name), 0)
                    occurrence[(form_id, name)] = nth + 1
                    row = named.setdefault(
                        (form_id, name, nth),
                        {
                            "label": (
                                f"{form_names[form_id]} · {name}"
                                if form_id in form_names
                                else name
                            ),
                            "values": [""] * len(bundle),
                        },
                    )
                    row["values"][level] = str(sub.get("desc") or "")
            rows += [
                {"label": row["label"], "values": row["values"][shown]}
                for row in named.values()
            ]
        return rows

    # 专武：每个 6★ 干员的第一把一档推荐武器（与社区攻略核对过）。
    signature = {
        cid: rec["weaponIds1"][0]
        for cid, rec in recommend.items()
        if chars.get(cid, {}).get("rarity") == 6 and rec.get("weaponIds1")
    }

    operators: dict[str, dict] = {}
    for cid, char in chars.items():
        name = text(char.get("name"))
        if not name:
            continue
        grow = growth.get(cid, {})
        levels = [
            {str(a["attrType"]): a["attrValue"] for a in row["Attribute"]["attrs"]}
            for row in char.get("attributes", [])
        ]
        top = next(
            (a for a in levels if round(a.get("0", 0)) == STAT_LEVEL),
            max(levels, key=lambda a: a.get("0", 0)) if levels else {},
        )
        stats = [(label, round(top.get(key, 0))) for key, label in BASE_ATTRS]
        stats += [
            (attr_names.get(k, k), round(top.get(k, 0)))
            for k in ("39", "40", "41", "42")
            if k in top
        ]

        # 每个天赋的最高节点：形态相关的效果要用它。
        top_talents: dict = {}
        for node in grow.get("talentNodeMap", {}).values():
            info = node.get("passiveSkillNodeInfo") or {}
            if node.get("nodeType") != 4 or not info.get("talentEffectId"):
                continue
            best = top_talents.get(info.get("index"))
            if best is None or (info.get("level", 0), info.get("breakStage", 0)) > (
                best.get("level", 0),
                best.get("breakStage", 0),
            ):
                top_talents[info.get("index")] = info
        talent_effects = [
            effects[info["talentEffectId"]]
            for info in top_talents.values()
            if info["talentEffectId"] in effects
        ]

        skill_rows = []
        groups = sorted(
            grow.get("skillGroupMap", {}).values(),
            key=lambda g: (
                SKILL_ORDER.index(g.get("skillGroupType", 0))
                if g.get("skillGroupType") in SKILL_ORDER
                else 9
            ),
        )
        for group in groups:
            values = max_level_values(group.get("skillIdList", []))
            # 技能在干员的两个形态下可能读法不同（诀：阵诀·智 / 阵诀·意），
            # 此时公共描述为空，全部内容都在形态里。
            forms = [
                {
                    "name": text(group.get(f"conditionName{n}")),
                    "when": rich_to_html(
                        strip_live_values(text(group.get(f"conditionDesc{n}")))
                        .removeprefix("/*")
                        .removesuffix("*/")
                        .strip()
                    ),
                    # 形态短文会重复开头的形态名（"阵诀·智：\n- ..."），这里已经是标题
                    "desc": rich_to_html(
                        fill_placeholders(
                            re.sub(
                                r"^<@[^<>]*>%s</>[：:]\n"
                                % re.escape(text(group.get(f"conditionName{n}"))),
                                "",
                                text(group.get(f"conditionPostDesc{n}")),
                            ),
                            values,
                        )
                    ),
                }
                for n in (1, 2)
                if group.get(f"conditionId{n}")
            ]
            skill_rows.append(
                {
                    "type": SKILL_TYPES.get(group.get("skillGroupType"), "技能"),
                    "name": text(group.get("name")),
                    "desc": rich_to_html(
                        fill_placeholders(text(group.get("desc")), values)
                    ),
                    "forms": [form for form in forms if form["desc"]],
                    "table": level_table(
                        group,
                        {
                            group[f"conditionId{n}"]: text(
                                group.get(f"conditionName{n}")
                            )
                            for n in (1, 2)
                            if group.get(f"conditionId{n}")
                        },
                        talent_effects,
                    ),
                    "icon": group.get("icon", ""),
                }
            )

        talents: dict[str, dict] = {}
        for node in grow.get("talentNodeMap", {}).values():
            info = node.get("passiveSkillNodeInfo", {})
            effect = effects.get(info.get("talentEffectId", ""))
            if not effect:
                continue
            tname = text(info.get("name"))
            if tname not in talents or info.get("level", 0) >= talents[tname]["level"]:
                talents[tname] = {
                    "level": info.get("level", 0),
                    "name": tname,
                    "desc": rich_to_html(
                        fill_placeholders(text(effect.get("desc")), effect_values(effect))
                    ),
                }

        potential_rows = []
        for bundle in potentials.get(cid, {}).get("potentialUnlockBundle", []):
            effect = effects.get(bundle.get("potentialEffectId", ""), {})
            potential_rows.append(
                {
                    "level": bundle.get("level"),
                    "name": text(bundle.get("name")),
                    "desc": rich_to_html(
                        fill_placeholders(text(effect.get("desc")), effect_values(effect))
                    ),
                }
            )

        operators[cid] = {
            "id": cid,
            "name": name,
            "eng": char.get("engName", ""),
            "rarity": char.get("rarity", 0),
            "profession": maps["profession_id_map"].get(str(char.get("profession")), ""),
            "weapon_type": maps["weapon_id_map"].get(str(char.get("weaponType")), ""),
            "element": maps["char_type_map"].get(char.get("charTypeId", ""), ""),
            "main_attr": attr_names.get(str(char.get("mainAttrType")), ""),
            "sub_attr": attr_names.get(str(char.get("subAttrType")), ""),
            "department": char.get("department", ""),
            "stats": stats,
            "skills": skill_rows,
            "talents": sorted(talents.values(), key=lambda t: t["name"]),
            "potentials": potential_rows,
            "logistics": logistics(cid),
            "signature_weapon": signature.get(cid),
            "recommended": [w for w in recommend.get(cid, {}).get("weaponIds1", [])],
        }

    owner_of = {
        wid: cid for cid, wid in signature.items() if not cid.startswith("chr_9000")
    }
    weapons: dict[str, dict] = {}
    for wid, basic in weapons_basic.items():
        item = items.get(wid, {})
        name = text(item.get("name"))
        if not name:
            continue
        curve = upgrades.get(basic.get("levelTemplateId", ""), {}).get("list", [])
        max_atk = max((row.get("baseAtk", 0) for row in curve), default=0)
        skill_rows = []
        for skill_id in basic.get("weaponSkillList", []):
            bundle = skills.get(skill_id, {}).get("SkillPatchDataBundle", [])
            if not bundle:
                continue
            levels = []
            for rank in bundle:
                values = {
                    e["key"].lower(): e["value"] for e in rank.get("blackboard", [])
                }
                levels.append(
                    rich_to_html(fill_placeholders(text(rank.get("description")), values))
                )
            skill_rows.append(
                {"name": text(bundle[0].get("skillName")), "levels": levels}
            )
        owner = owner_of.get(wid)
        weapons[wid] = {
            "id": wid,
            "name": name,
            "eng": text(basic.get("engName")) or basic.get("engName", ""),
            "rarity": basic.get("rarity", 0),
            "type": maps["weapon_id_map"].get(str(basic.get("weaponType")), ""),
            "max_atk": max_atk,
            "max_lv": basic.get("maxLv", 0),
            "icon": item.get("iconId") or wid,
            "deco": text(item.get("decoDesc")),
            "owner": operators[owner]["name"] if owner in operators else "",
            "skills": skill_rows,
        }

    return {
        "schema": INDEX_SCHEMA,
        "version": version.get("id", ""),
        "published_at": version.get("publishedAt", ""),
        "operators": operators,
        "weapons": weapons,
        "equip_sets": build_equip_sets(load, text, maps),
        "equip_items": build_equip_items(load, text, maps),
        "endgame": build_endgame(load, text, maps, table_dir),
        "leaders": build_leaders(load, text),
        "dungeons": build_dungeons(load, text, maps),
        "enemies": build_enemies(load, text, maps),
        "calendar": build_calendar(load, text),
    }


def index_counts(index: dict) -> dict[str, int]:
    """契约里的 counts：各类资料的条目数量，缺失一律为 0。"""

    def size(key: str) -> int:
        value = index.get(key)
        if isinstance(value, (dict, list)):
            return len(value)
        return 0

    return {
        "characters": size("operators"),
        "weapons": size("weapons"),
        "equipSuits": size("equip_sets"),
        "dungeons": size("dungeons"),
        "enemies": size("enemies"),
        "activities": len((index.get("calendar") or {}).get("activities") or []),
    }


def stage_stats(index: dict) -> dict[str, int]:
    """终局关卡敌人统计；foes_plain 应接近 0，突增说明 spawner 文件与关卡对不上了。"""
    endgame = index.get("endgame") or {}
    stages = [
        s for g in (endgame.get("tower") or {}).values() for s in g.get("stages", [])
    ]
    stages += [
        s
        for m in endgame.get("monument") or []
        for g in m.get("groups", [])
        for s in g.get("stages", [])
    ]
    foes = [foe for s in stages for foe in s.get("enemies", [])]
    return {
        "stages": len(stages),
        "foes": len(foes),
        "foes_plain": sum(1 for f in foes if f.get("plain")),
    }


def build_endgame(load, text, maps: dict, table_dir: Path) -> dict:
    """战争回响（赛季塔）与影拓丰碑（高难系列）的关卡索引。"""
    dungeons, series = load("DungeonTable"), load("DungeonSeriesTable")
    enemies = load("EnemyTemplateDisplayInfoTable")
    enemy_rows, enemy_attrs = load("EnemyTable"), load("EnemyAttributeTemplateTable")
    tower_groups, tower_seasons, tower_buffs = (
        load("SeasonTowerGameGroupTable"),
        load("SeasonTowerTable"),
        load("SeasonTowerDungeonTable"),
    )
    time_ranges = load("TimeRangeTable")
    attr_ids = {name: int(key) for key, name in maps["ATTR_MAP_EN"].items()}
    attr_names = {
        int(key): name for key, name in maps["ATTR_MAP"].items() if str(key).isdigit()
    }
    formulas = {name: int(key) for key, name in maps["MODIFIER_TYPE_MAP"].items()}
    scene_use = Counter(
        (dungeons[s].get("sceneId"), level)
        for s in endgame_stage_ids(series, tower_groups)
        if s in dungeons
        for level in set(dungeons[s].get("enemyLevels", []))
    )
    spawner_cache: dict[str, list[dict]] = {}
    buff_cache: dict[str, dict] = {}

    def base_name(stage_id: str) -> str:
        return text(dungeons.get(stage_id, {}).get("dungeonName")).split("·")[0].strip()

    def spawners(scene: str) -> list[dict]:
        if scene not in spawner_cache:
            folder = table_dir / "SpawnerConfig" / scene
            spawner_cache[scene] = (
                [json.loads(p.read_text("utf-8")) for p in sorted(folder.glob("*.json"))]
                if scene and folder.is_dir()
                else []
            )
        return spawner_cache[scene]

    def effects(
        buff_id: str, blackboard: list | None = None
    ) -> tuple[list[dict], dict[int, float]]:
        if buff_id not in buff_cache:
            file = table_dir / "BuffData" / f"{buff_id}.json"
            buff_cache[buff_id] = (
                json.loads(file.read_text("utf-8")) if file.is_file() else {}
            )
        return buff_effects(buff_cache[buff_id], blackboard, attr_ids, formulas)

    def template_of(enemy_id: str) -> str:
        return enemy_rows.get(enemy_id, {}).get("templateId") or enemy_id

    def buff(buff_id: str) -> dict:
        effects(buff_id)
        return buff_cache[buff_id]

    def scenery(entry: dict) -> bool:
        """出生即隐藏血条：属于关卡机制的一部分，不是要击败的敌人。"""
        born = list(enemy_rows.get(entry["enemyId"], {}).get("bornBuffs") or []) + [
            b.get("buffId", "") for b in entry.get("bornBuffList") or []
        ]
        return any(hides_health_bar(buff(buff_id)) for buff_id in born)

    def display(enemy_id: str) -> tuple[str, str]:
        probe = template_of(enemy_id)
        name = text(enemies.get(probe, {}).get("name"))
        if not name:
            # 表里没有这一行：关卡专属变体会追加后缀，例如 eny_0118_klhog_hdg026
            probe = enemy_id
            while probe and not (name := text(enemies.get(probe, {}).get("name"))):
                probe = probe.rpartition("_")[0] if probe.count("_") > 2 else ""
        return (name, probe) if name else (enemy_id, "")

    def spawned(row: dict, pairs: list[tuple[str, int]]) -> list[dict]:
        """本关 spawner 的敌人条目：变体、等级，以及出生时带的 buff。"""
        scene, levels = row.get("sceneId", ""), {level for _, level in pairs}
        templates = {template_of(enemy_id) for enemy_id, _ in pairs}
        shared = any(scene_use[(scene, level)] > 1 for level in levels)
        library = []
        for config in spawners(scene):
            used = {
                action.get("libraryKey")
                for wave in (config.get("waveMap") or {}).values()
                for group in (wave.get("groupMap") or {}).values()
                for action in (group.get("actionMap") or {}).values()
            } - {None, ""}
            entries = [
                e
                for e in config.get("enemyLibrary") or []
                if e.get("enemyLevel") in levels and (not used or e.get("key") in used)
            ]
            # 战争回响的全部关卡共用一个场景，此时只有列出了全部刷怪的 spawner
            # 才是本关的。
            if shared and any(template_of(e["enemyId"]) not in templates for e in entries):
                continue
            library += entries
        return library

    def stage(stage_id: str, difficulty: str) -> dict:
        row = dungeons.get(stage_id, {})
        pairs = list(
            dict.fromkeys(zip(row.get("enemyIds", []), row.get("enemyLevels", [])))
        )
        listed = {enemy_id for enemy_id, _ in pairs}
        # 布景敌人的等级在各难度间保持一致，因此在整个场景里找。
        props = [
            e
            for config in spawners(row.get("sceneId", ""))
            for e in config.get("enemyLibrary") or []
            if scenery(e)
        ]
        library = [e for e in spawned(row, pairs) if not scenery(e)]
        # (变体, 等级) -> (展示成哪个敌人, 它的 spawner 条目)
        rows: dict[tuple[str, int], tuple[str, list[dict]]] = {}
        taken = []
        for enemy_id, level in pairs:
            same_level = [e for e in library if e["enemyLevel"] == level]
            # 关卡里要么列出确切变体，要么只列出变体所属的基础敌人。
            found = [e for e in same_level if e["enemyId"] == enemy_id] or [
                e
                for e in same_level
                if e["enemyId"] not in listed
                and template_of(e["enemyId"]) == template_of(enemy_id)
            ]
            taken += found
            if not found and any(
                template_of(e["enemyId"]) == template_of(enemy_id) for e in props
            ):
                continue  # 游戏列出了它，但它在本关只是布景
            for variant in list(dict.fromkeys(e["enemyId"] for e in found)) or [enemy_id]:
                rows[(variant, level)] = (
                    enemy_id,
                    [e for e in found if e["enemyId"] == variant],
                )
        for entry in library:  # 刷出来了但不在关卡敌人列表里
            if not any(entry is e for e in taken):
                rows.setdefault(
                    (entry["enemyId"], entry["enemyLevel"]), (entry["enemyId"], [])
                )[1].append(entry)
        foes = []
        for (variant, level), (shown, entries) in rows.items():
            born: list[dict] = []
            for entry in entries:
                # 与 AKEData 站点一致：同一变体一行，合并全部刷怪的 buff，
                # 每个 buff 只出现一次。
                born += [
                    b
                    for b in entry.get("bornBuffList") or []
                    if b.get("buffId") not in {x.get("buffId") for x in born}
                ]
            name, icon = display(shown)
            enemy = enemy_rows.get(variant, {})
            own = [effects(b) for b in enemy.get("bornBuffs") or []]
            placed = [effects(b.get("buffId", ""), b.get("blackboard")) for b in born]
            foe = {
                "name": name,
                "icon": icon,
                "level": level,
                **enemy_stats(enemy, enemy_attrs, level, own + placed),
            }
            # 上面数值已经包含的内容，按 AKEData 站点的措辞标注：敌人变体自带的加成
            # （born）与关卡 spawner 追加的（buff）。
            born_notes = modifier_notes(
                list(enemy.get("attrModifiers") or [])
                + [m for mods, _ in own for m in mods],
                attr_names,
            )
            buff_notes = modifier_notes(
                [m for mods, _ in placed for m in mods], attr_names
            ) + override_notes(placed, attr_names)
            if born_notes:
                foe["born"] = born_notes
            if buff_notes:
                foe["buff"] = buff_notes
            if not entries:  # spawner 没有放置（战斗中召唤）：只有敌人自身数值
                foe["plain"] = True
            if foe not in foes:
                foes.append(foe)
        buff = text(tower_buffs.get(stage_id, {}).get("specialBuffDesc"))
        params = {
            p["key"].lower(): p["value"] for p in row.get("paramList") or [] if "key" in p
        }
        return {
            "id": stage_id,
            "difficulty": difficulty,
            "recommend_lv": row.get("recommendLv", 0),
            "feature": rich_to_html(
                fill_placeholders(text(row.get("featureDesc")), params)
            ),
            "special_buff": rich_to_html(fill_placeholders(buff, params)) if buff else "",
            "enemies": foes,
        }

    tower = {}
    for group_id, group in tower_groups.items():
        stars = group.get("stars", {})
        first = stars.get("1", {}).get("gameId", group_id)
        tower[group_id] = {
            "id": group_id,
            "name": base_name(first),
            "mode": "战争回响",
            "cover": group.get("icon", ""),
            "stages": [
                stage(stars[k]["gameId"], TOWER_DIFFICULTIES.get(k, k))
                for k in sorted(stars)
                if stars[k].get("gameId")
            ],
        }

    seasons = []
    for season_id, season in sorted(tower_seasons.items(), key=lambda kv: int(kv[0])):
        weeks = []
        for week_id, week in sorted(
            season.get("weeks", {}).items(), key=lambda kv: int(kv[0])
        ):
            ranges = time_ranges.get(
                f"time_activity_seasontower_season_{season_id}_week_{week_id}", {}
            ).get("timeRangeList", [])
            weeks.append(
                {
                    "week": int(week_id),
                    "name": text(week.get("weekShowName")),
                    "groups": week.get("includeGameIdList", []),
                    "open": ranges[0]["openTime"] if ranges else "",
                    "close": ranges[0]["closeTime"] if ranges else "",
                }
            )
        seasons.append(
            {"id": int(season_id), "name": text(season.get("name")), "weeks": weeks}
        )

    monument = []
    for series_id, row in sorted(series.items(), key=lambda kv: kv[1].get("sortId", 0)):
        if row.get("gameCategory") != "dungeon_highdifficulty":
            continue
        stage_ids = row.get("includeDungeonIds", [])
        groups = []
        for base in [sid for sid in stage_ids if not sid.endswith("_s")]:
            variants = [stage(base, "普通")] + (
                [stage(base + "_s", "苦难")] if base + "_s" in stage_ids else []
            )
            groups.append(
                {
                    "id": base,
                    "name": base_name(base),
                    "mode": "影拓丰碑",
                    "series": text(row.get("name")),
                    "cover": dungeons.get(base, {}).get("dungeonPicPath", ""),
                    "stages": variants,
                }
            )
        monument.append({"id": series_id, "name": text(row.get("name")), "groups": groups})

    return {"tower": tower, "tower_seasons": seasons, "monument": monument}


def _blackboard(rows: list | None) -> dict[str, float]:
    """黑板行的数值放在几个带类型的键之一。"""
    values = {}
    for row in rows or []:
        values[row.get("key")] = next(
            (
                row[k]
                for k in ("valueFloat", "valueDouble", "valueInt", "valueLong", "value")
                if row.get(k) is not None
            ),
            0.0,
        )
    return values


def buff_effects(
    buff: dict, blackboard: list | None, attr_ids: dict[str, int], formulas: dict[str, int]
) -> tuple[list[dict], dict[int, float]]:
    """一个 buff 在持续期间对持有者属性的作用：(取模器, 原始覆盖值)。

    取模器的形状与 EnemyTable.attrModifiers 相同；覆盖值直接替换原始属性，关卡就是
    用这种方式统一各元素抗性。blackboard 是 spawner 传入的替换值。
    """
    values = {**_blackboard(buff.get("blackboard")), **_blackboard(blackboard)}

    def number(param: dict) -> float:
        if param.get("useBlackboardKey") and param.get("blackboardKey"):
            return values.get(param["blackboardKey"], param.get("value", 0.0))
        return param.get("value", 0.0)

    modifiers = []
    for mod in (buff.get("attributeModifier") or {}).get("attributeModifiers") or []:
        attr, formula = attr_ids.get(mod.get("attributeType")), formulas.get(
            mod.get("formulaItem")
        )
        if attr is not None and formula is not None:
            modifiers.append(
                {
                    "attrType": attr,
                    "modifierType": formula,
                    "attrValue": number(mod.get("param") or {}),
                }
            )
    overrides = {}
    for event in buff.get("buffEventAction") or []:
        if event.get("buffEvent") != "DuringBuffEnable":
            continue
        for group in event.get("actions") or []:
            for action in group.get("actionData") or []:
                if "OverrideRawAttributeAction" not in action.get("$type", ""):
                    continue
                for item in action.get("attributeOverrides") or []:
                    attr = attr_ids.get(item.get("attributeType"))
                    if attr is not None:
                        overrides[attr] = number(item.get("overrideValue") or {})
    return modifiers, overrides


# modifierType -> 运算，顺序照 AKEData 站点：先是 Base* 类，百分比为 x(1 + value)
# 且多个相乘。站点是这些数值的对照基准，因此叠加顺序与它完全一致。
MODIFIER_STEPS = (
    (5, "add"),
    (6, "percent"),
    (7, "add"),
    (8, "factor"),
    (3, "add"),
    (4, "factor"),
    (0, "add"),
    (1, "percent"),
)
MODIFIER_KINDS = dict(MODIFIER_STEPS)
LEGACY_RESISTANCES = {80, 81, 82, 83, 84, 85}  # *DmgResistScalar：站点不算进加成行
BALANCED_RESISTANCES = (94, 95, 96, 97, 98)  # 关卡统一取值的五种元素（超域保持原样）


def hides_health_bar(buff: dict) -> bool:
    """永久 buff 且强制隐藏持有者血条。"""
    return buff.get("lifeType") == "Infinity" and any(
        "ForceHideHeadBarAction" in action.get("$type", "")
        for event in buff.get("buffEventAction") or []
        if event.get("buffEvent") == "DuringBuffEnable"
        for group in event.get("actions") or []
        for action in group.get("actionData") or []
    )


def modified(value: float, modifiers: list[dict], attr: int) -> float:
    """对单个属性套用取模器（见 MODIFIER_STEPS）。"""
    for kind, step in MODIFIER_STEPS:
        for mod in modifiers:
            if mod.get("attrType") != attr or mod.get("modifierType") != kind:
                continue
            amount = mod.get("attrValue", 0.0)
            value = (
                value + amount
                if step == "add"
                else value * (1 + amount)
                if step == "percent"
                else value * amount
            )
    return value


def _number(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def modifier_notes(modifiers: list[dict], attr_names: dict[int, str]) -> list[str]:
    """属性取模器写成 "最大生命值 +60%" / "失衡值上限 +40"，每个属性每种运算一条。

    分组与措辞与 AKEData 站点一致：同属性的百分比复合，倍率相乘后也按百分比展示，
    其余相加。
    """
    merged: dict[tuple[int, int], float] = {}
    for mod in modifiers:
        key, amount = (
            (mod.get("attrType"), mod.get("modifierType")),
            mod.get("attrValue", 0.0),
        )
        if key[0] in LEGACY_RESISTANCES or key[0] not in attr_names or key[1] not in MODIFIER_KINDS:
            continue
        step = MODIFIER_KINDS[key[1]]
        if key not in merged:
            merged[key] = amount
        elif step == "percent":
            merged[key] = (1 + merged[key]) * (1 + amount) - 1
        elif step == "factor":
            merged[key] *= amount
        else:
            merged[key] += amount
    notes = []
    for (attr, kind), amount in merged.items():
        step = MODIFIER_KINDS[kind]
        amount = amount - 1 if step == "factor" else amount
        shown = (
            f"{_number(amount * 100)}%" if step in ("percent", "factor") else _number(amount)
        )
        notes.append(f"{attr_names[attr]} {'+' if amount > 0 else ''}{shown}")
    return notes


def override_notes(
    effects: list[tuple[list[dict], dict[int, float]]], attr_names: dict[int, str]
) -> list[str]:
    """关卡直接指定的原始属性；被统一取值的元素抗性合并成一行。"""
    overrides = {attr: value for _, sets in effects for attr, value in sets.items()}
    levelled = {overrides.get(attr) for attr in BALANCED_RESISTANCES}
    notes = []
    if len(levelled) == 1 and None not in levelled:
        notes.append(f"属性抗性统一为 {_number(levelled.pop())}")
        overrides = {
            attr: value
            for attr, value in overrides.items()
            if attr not in BALANCED_RESISTANCES
        }
    return notes + [
        f"{attr_names[attr]} 固定为 {_number(value)}"
        for attr, value in overrides.items()
        if attr in attr_names
    ]


def enemy_stats(
    row: dict,
    templates: dict,
    level: int,
    effects: list[tuple[list[dict], dict[int, float]]] | tuple = (),
) -> dict:
    """敌人在关卡等级下的生命值 / 攻击力 / 防御 / 失衡值上限与非零抗性。

    会把敌人自身的 attrModifiers 与它出生时携带 buff 的 effects（见 buff_effects）
    计入。关卡级 buff（special_buff 文本）不计入。
    """
    template = templates.get(row.get("attrTemplateId", ""), {})
    per_level = template.get("levelDependentAttributes") or []
    if not 0 < level <= len(per_level):
        return {}
    base = {
        a["attrType"]: a["attrValue"]
        for a in (template.get("levelIndependentAttributes") or {}).get("attrs", [])
    }
    base.update({a["attrType"]: a["attrValue"] for a in per_level[level - 1]["attrs"]})
    modifiers = list(row.get("attrModifiers") or [])
    for buff_modifiers, overrides in effects:
        modifiers += buff_modifiers
        base.update(overrides)
    stats = {
        key: round(modified(base.get(attr, 0.0), modifiers, attr))
        for attr, key in ((1, "hp"), (2, "atk"), (3, "def"), (20, "poise"))
    }
    stats["res"] = [
        [label, value]
        for attr, label in ENEMY_RESISTANCES
        if (value := round(modified(base.get(attr, 0.0), modifiers, attr)))
    ]
    return stats


LEADER_TYPE = 2  # EnemyTemplateDisplayInfoTable.displayType：领袖敌人
BOSS_CHALLENGE = "dungeon_bossrush"  # 危境遗影 / 延影 / 祸影 / 狂影：每档一个副本


def build_leaders(load, text) -> list[dict]:
    """全部领袖敌人，含特性与它在各档位挑战中的默认属性。

    "默认"指敌人自身属性模板在该等级下的值，与 AKEData 敌人页一致；关卡额外叠加的
    （spawner buff）属于关卡敌人页。没有专属挑战的敌人（某场战斗的阶段或部位）按
    STAT_LEVEL 展示。
    """
    displays, rows, templates = (
        load("EnemyTemplateDisplayInfoTable"),
        load("EnemyTable"),
        load("EnemyAttributeTemplateTable"),
    )
    abilities, dungeons = load("EnemyAbilityDescTable"), load("DungeonTable")
    template_of = {
        enemy_id: row.get("templateId") or enemy_id for enemy_id, row in rows.items()
    }
    tiers: dict[str, list[tuple[str, dict, int]]] = {}
    for dungeon_id, dungeon in sorted(dungeons.items()):
        if dungeon.get("dungeonCategory") != BOSS_CHALLENGE:
            continue
        for enemy_id, level in zip(
            dungeon.get("enemyIds") or [], dungeon.get("enemyLevels") or []
        ):
            tiers.setdefault(template_of.get(enemy_id, enemy_id), []).append(
                (dungeon_id, dungeon, int(level))
            )
    leaders = []
    for template, display in displays.items():
        if display.get("displayType") != LEADER_TYPE:
            continue
        row = rows.get(template) or {"attrTemplateId": template}
        levels = [
            {
                "tier": text(d.get("dungeonLevelDesc")),
                "stage": text(d.get("dungeonName")),
                "level": level,
                **enemy_stats(row, templates, level),
            }
            for _, d, level in tiers.get(template, [])
        ] or [
            {
                "tier": "",
                "stage": "",
                "level": STAT_LEVEL,
                **enemy_stats(row, templates, STAT_LEVEL),
            }
        ]
        leaders.append(
            {
                "id": template,
                "name": text(display.get("name")),
                "desc": text(display.get("description")),
                "traits": [
                    t
                    for a in display.get("abilityDescIds") or []
                    if (t := text((abilities.get(a) or {}).get("description")))
                ],
                "challenge": bool(tiers.get(template)),
                "levels": levels,
            }
        )
    return leaders


def build_dungeons(load, text, maps) -> list[dict]:
    """全部关卡的扁平索引，供检索与档案卡使用（上游没有这一层，为 /api/wiki 新增）。

    只取 DungeonTable 的展示字段；敌人数值属于 endgame 与 enemies 两张表。
    """
    dungeons = load("DungeonTable")
    rows = []
    for dungeon_id, row in dungeons.items():
        name = text(row.get("dungeonName"))
        if not name:
            continue
        params = {
            p["key"].lower(): p["value"] for p in row.get("paramList") or [] if "key" in p
        }
        category = row.get("dungeonCategory") or ""
        rows.append(
            {
                "id": dungeon_id,
                "name": name,
                "base_name": name.split("·")[0].strip(),
                "level_desc": text(row.get("dungeonLevelDesc")),
                "category": DUNGEON_KINDS.get(category, category),
                "recommend_lv": row.get("recommendLv", 0),
                "scene": row.get("sceneId", ""),
                "levels": sorted({lv for lv in row.get("enemyLevels") or [] if lv}),
                "enemy_count": len({e for e in row.get("enemyIds") or [] if e}),
                "feature": rich_to_html(
                    fill_placeholders(text(row.get("featureDesc")), params)
                ),
            }
        )
    return sorted(rows, key=lambda r: (r["base_name"], r["name"]))


def build_enemies(load, text, maps) -> list[dict]:
    """敌人图鉴的扁平索引；数值为该敌人自身模板在 STAT_LEVEL 下的默认值。

    上游只用 EnemyTemplateDisplayInfoTable 找领袖敌人（leaders）。这里的行是给检索
    与档案卡用的清单，数值缺失时留空字典，由视图层转成空字符串。
    """
    displays, rows, templates = (
        load("EnemyTemplateDisplayInfoTable"),
        load("EnemyTable"),
        load("EnemyAttributeTemplateTable"),
    )
    abilities = load("EnemyAbilityDescTable")
    out = []
    for template, display in displays.items():
        name = text(display.get("name"))
        if not name:
            continue
        row = rows.get(template) or {"attrTemplateId": template}
        out.append(
            {
                "id": template,
                "name": name,
                "desc": text(display.get("description")),
                "template": display.get("templateId") or template,
                "leader": display.get("displayType") == LEADER_TYPE,
                "traits": [
                    t
                    for a in display.get("abilityDescIds") or []
                    if (t := text((abilities.get(a) or {}).get("description")))
                ],
                "stats": enemy_stats(row, templates, STAT_LEVEL),
            }
        )
    return sorted(out, key=lambda e: (not e["leader"], e["name"]))


def stage_cover_url(group: dict) -> str:
    """关卡封面：影拓丰碑用场景图（20 MB PNG），战争回响用敌人立绘。"""
    folder = "seasontower" if group.get("mode") == "战争回响" else "dungeon"
    return f"{IMAGE_BASE}/{folder}/{group['cover']}.png" if group.get("cover") else ""


def enemy_icon_url(enemy_id: str) -> str:
    if not enemy_id:
        return ""
    return f"{IMAGE_BASE}/monstericonbig/{enemy_id}.png"


def build_calendar(load, text) -> dict:
    """活动、卡池与战令周任务及它们的开闭时间（Asia/Shanghai）。"""
    ranges = load("TimeRangeTable")
    chars, items = load("CharacterTable"), load("ItemTable")  # 武器名在 ItemTable 里

    def window(*time_ids: str) -> tuple[str, str] | None:
        for time_id in time_ids:
            spans = (ranges.get(time_id) or {}).get("timeRangeList") or []
            if time_id and spans and spans[0].get("openTime"):
                return spans[0]["openTime"], spans[0].get("closeTime", "")
        return None

    activities = []
    for activity_id, row in load("ActivityTable").items():
        span, name = window(row.get("timeId", "")), text(row.get("name"))
        if span and name:
            # tab / colour：游戏在活动页签上展示的横幅（sprites/activity/<tab>.png）
            # 与其主题色
            activities.append(
                {
                    "id": activity_id,
                    "name": name,
                    "open": span[0],
                    "close": span[1],
                    "tab": row.get("tabImg") or "",
                    "color": row.get("tabImgColor") or "",
                }
            )

    pools = []
    for kind, table, up_key, names in (
        ("char", "GachaCharPoolTable", "upCharIds", chars),
        ("weapon", "GachaWeaponPoolTable", "upWeaponIds", items),
    ):
        for pool_id, row in load(table).items():
            suffix = re.search(r"(\d+_\d+_\d+)$", row.get("nameImage") or "")
            span = window(
                f"time_{pool_id.replace('weponbox', 'weaponbox')}",
                row.get("clientTopTimeId", ""),
                f"time_rerun_{suffix.group(1)}" if suffix else "",
            )
            if not span or not span[1]:  # 常驻池（标准、新手、固定武器箱）没有截止时间
                continue
            up = [text(names.get(i, {}).get("name")) or i for i in row.get(up_key) or []]
            pools.append(
                {
                    "id": pool_id,
                    "kind": kind,
                    "name": text(row.get("name")),
                    "up": up,
                    "open": span[0],
                    "close": span[1],
                }
            )

    tasks, conditions = load("BattlePassTaskTable"), load("BattlePassConditionTable")
    passes = []
    for time_id in sorted(k for k in ranges if re.fullmatch(r"time_bp_\d+", k)):
        bp, span = time_id.removeprefix("time_"), window(time_id)
        if not span:
            continue
        weeks = []
        for week in range(1, 13):
            rows = sorted(
                (
                    t
                    for t in tasks.values()
                    if t.get("groupId") == f"{bp}_taskgroup_weekly_{week}"
                ),
                key=lambda t: t.get("sortId", 0),
            )
            if not rows:
                break
            opened = (
                span[0]
                if week == 1
                else (window(f"time_{bp}_sublabel_week_{week}") or ("", ""))[0]
            )
            names = []
            for row in rows:
                goal = (conditions.get((row.get("conditionIds") or [""])[0]) or {}).get(
                    "progressToCompare", ""
                )
                names.append(
                    re.sub(r"<[^<>]*>", "", text(row.get("name")).replace("%d", str(goal)))
                )
            weeks.append({"week": week, "open": opened, "tasks": names})
        passes.append({"id": bp, "open": span[0], "close": span[1], "weeks": weeks})
    # 每周事务（activity_weekly_task_1）：任务 id 形如 "week{N}_..."，
    # 第 N 周自开放起顺延 (N-1)*7 天。
    weekly_activity = load("ActivityTable").get("activity_weekly_task_1", {})
    weekly_span = window(weekly_activity.get("timeId", ""))
    weekly_weeks: dict[str, list] = {}
    for row in sorted(
        load("ActivityWeeklyTaskTable").values(), key=lambda r: r.get("sortId", 0)
    ):
        week = re.match(r"week(\d+)_", str(row.get("taskId", "")))
        if row.get("activityId") != "activity_weekly_task_1" or not week:
            continue
        factor = row.get("displayFactor")
        target = (row.get("progressToCompare") or 0) * (1 if factor is None else factor)
        target_text = str(int(target)) if float(target).is_integer() else f"{target:g}"
        desc = re.sub(
            r"<[^<>]*>",
            "",
            re.sub(r"%[-+0-9.]*[dfs]", target_text, text(row.get("desc"))),
        )
        weekly_weeks.setdefault(week.group(1), []).append(
            {"desc": desc, "score": row.get("score", 0)}
        )
    milestones = (
        (load("ActivityWeeklyTaskMileStoneTable").get("activity_weekly_task_1") or {}).get(
            "mileStones"
        )
        or {}
    )
    weekly = {
        "name": text(weekly_activity.get("name")) or "每周事务",
        "open": weekly_span[0] if weekly_span else "",
        "weeks": weekly_weeks,
        "milestones": sorted(m.get("score", 0) for m in milestones.values()),
    }
    versions = []
    for time_id in ranges:
        match = re.fullmatch(r"time_version_v(\d+)d(\d+)", time_id)
        span = window(time_id) if match else None
        if span:
            versions.append(
                {
                    "name": f"{match.group(1)}.{match.group(2)}",
                    "open": span[0],
                    "close": span[1],
                }
            )
    return {
        "activities": activities,
        "pools": pools,
        "passes": passes,
        "weekly": weekly,
        "versions": versions,
        "gifts": build_gacha_gifts(load, text),
    }


def build_gacha_gifts(load, text) -> dict:
    """卡池 id -> 该池抽数里程碑自动赠送的内容（不是抽到的）。

    每条为 {"at": 首次触发抽数, "every": 间隔，0 表示一次性, "items": [{"name",
    "icon"}]}；循环赠送会依次轮换其条目（武器池：补给箱、UP 武器、补给箱……）。抽数按
    付费抽计数，免费十连不计入。icon 是该赠送对应的干员 / 武器 id，没有则为空。
    """
    rewards, items = load("RewardTable"), load("ItemTable")

    def gift(reward_id: str) -> dict | None:
        bundles = (rewards.get(reward_id) or {}).get("itemBundles") or []
        item_id = bundles[0].get("id", "") if bundles else ""
        name = text((items.get(item_id) or {}).get("name"))
        if not name:
            return None
        count = bundles[0].get("count", 1)
        icon = (
            item_id
            if item_id.startswith("wpn_")
            else item_id.removeprefix("item_charpotentialup_")
            if item_id.startswith("item_charpotentialup_")
            else ""
        )
        return {"name": f"{name}×{count}" if count > 1 else name, "icon": icon}

    def entry(at: int, every: int, reward_ids: list[str]) -> dict | None:
        found = [g for g in map(gift, reward_ids) if g]
        return (
            {"at": at, "every": every, "items": found}
            if at > 0 and found and len(found) == len(reward_ids)
            else None
        )

    result: dict[str, list] = {}
    for table, type_table in (
        ("GachaCharPoolTable", "GachaCharPoolTypeTable"),
        ("GachaWeaponPoolTable", "GachaWeaponPoolTypeTable"),
    ):
        types = load(type_table)
        for pool_id, row in load(table).items():
            rule = types.get(str(row.get("type"))) or {}
            every = rule.get("intervalAutoRewardPerPullCount") or 0
            entries = [
                entry(
                    rule.get("intervalAutoRewardStartPullCount", 0) + every,
                    every,
                    row.get("intervalAutoRewardIds") or [],
                )
                if every
                else None,
                entry(
                    rule.get("onceRewardIdPullCount") or 0,
                    0,
                    [row.get("onceRewardId") or ""],
                ),
                entry(
                    rule.get("onceRewardId2PullCount") or 0,
                    0,
                    [row.get("onceRewardId2") or ""],
                ),
                *(
                    entry(at, 0, [reward_id])
                    for at, reward_id in zip(
                        rule.get("cumulativeRewardsPullCount") or [],
                        row.get("cumulativeRewardIds") or [],
                    )
                ),
            ]
            if any(entries):
                result[pool_id] = sorted((e for e in entries if e), key=lambda e: e["at"])
    return result


def _equip_value(value: float, modifier: int, flat: bool) -> str:
    """按取模类型（maps.MODIFIER_TYPE_MAP）展示：5 / 7 相加，6 乘基础值，
    8 缩放承受伤害（0.96 = 少受 4%）。"""
    if modifier == 8:
        return f"{(1 - value) * 100:.1f}%"
    if modifier == 6 or not flat:
        return f"{value * 100:.1f}%"
    return f"{value:.1f}".removesuffix(".0")


def _equip_attrs(equip: dict, maps: dict) -> list[dict]:
    """一件装备的三条可精炼属性，按游戏内顺序（attrIndex 1..3）。"""
    attrs = []
    for mod in equip.get("displayAttrModifiers") or []:
        composite = mod.get("compositeAttr") or ""
        flat = mod.get("attrType") in EQUIP_FLAT_ATTRS or composite in ("Main", "Sub")
        enhanced = mod.get("enhancedAttrValues") or []
        attrs.append(
            {
                "name": maps["COMPOSITE_NAME_MAP"].get(composite)
                or maps["ATTR_MAP"].get(str(mod.get("attrType")), ""),
                "base": _equip_value(
                    mod.get("attrValue", 0.0), mod.get("modifierType"), flat
                ),
                "max": (
                    _equip_value(enhanced[-1], mod.get("modifierType"), flat)
                    if enhanced
                    else ""
                ),
            }
        )
    return attrs


def build_equip_items(load, text, maps) -> dict:
    """按名字索引的每件装备（套装件与散件）：图标与属性名，供配装统计使用。"""
    equips, items = load("EquipTable"), load("ItemTable")
    result: dict[str, dict] = {}
    for equip_id, equip in equips.items():
        item = items.get(equip_id, {})
        name = text(item.get("name"))
        if name:
            result.setdefault(
                name,
                {
                    "icon": item.get("iconId") or equip_id,
                    "attrs": [a["name"] for a in _equip_attrs(equip, maps)],
                },
            )
    return result


def build_equip_sets(load, text, maps) -> dict:
    """装备套装：3 件套效果，以及每件装备强化前后的属性。"""
    equips, items, skills = load("EquipTable"), load("ItemTable"), load("SkillPatchTable")
    sets: dict[str, dict] = {}
    for set_id, row in load("EquipSuitTable").items():
        rule = (row.get("list") or [{}])[0]
        name = text(rule.get("suitName"))
        bundle = skills.get(rule.get("skillID", ""), {}).get("SkillPatchDataBundle", [])
        if not name or not bundle:
            continue
        rank = bundle[min(max(rule.get("skillLv", 1), 1), len(bundle)) - 1]
        values = {e["key"].lower(): e["value"] for e in rank.get("blackboard", [])}
        pieces = []
        for equip_id in row.get("equipList") or []:
            equip, item = equips.get(equip_id), items.get(equip_id, {})
            piece_name = text(item.get("name"))
            if not equip or not piece_name:
                continue
            pieces.append(
                {
                    "id": equip_id,
                    "name": piece_name,
                    "part": EQUIP_PARTS.get(equip.get("partType"), ""),
                    "rarity": item.get("rarity", 0),
                    "level": equip.get("minWearLv", 0),
                    "icon": item.get("iconId") or equip_id,
                    "defense": round(
                        (equip.get("displayBaseAttrModifier") or {}).get("attrValue", 0)
                    ),
                    "domain": maps["DOMAIN_MAP"].get(equip.get("domainId", ""), ""),
                    "attrs": _equip_attrs(equip, maps),
                }
            )
        if not pieces:
            continue
        order = list(EQUIP_PARTS.values())
        pieces.sort(
            key=lambda p: (
                -p["rarity"],
                order.index(p["part"]) if p["part"] in order else 9,
                p["id"],
            )
        )
        sets[set_id] = {
            "id": set_id,
            "name": name,
            "count": rule.get("equipCnt", 3),
            "effect": rich_to_html(fill_placeholders(text(rank.get("description")), values)),
            "rarity": pieces[0]["rarity"],
            "level": max(p["level"] for p in pieces),
            "domain": pieces[0]["domain"],
            "pieces": pieces,
        }
    return sets


def activity_banner_url(tab: str) -> str:
    if not tab:
        return ""
    return f"{IMAGE_BASE}/activity/{tab}.png"


def equip_icon_url(icon_id: str) -> str:
    if not icon_id:
        return ""
    return f"{IMAGE_BASE}/itemicon/{icon_id}.png"


def logistics_icon_url(icon_id: str) -> str:
    if not icon_id:
        return ""
    return f"{IMAGE_BASE}/spaceship/spaceshipskillicon/{icon_id}.png"


def char_icon_url(char_id: str) -> str:
    if not char_id:
        return ""
    return f"{IMAGE_BASE}/charremoteicon/icon_{char_id}.png"


def weapon_icon_url(icon_id: str) -> str:
    if not icon_id:
        return ""
    return f"{IMAGE_BASE}/itemiconbig/{icon_id}.png"


def remove_tree(path: Path) -> None:
    """删除同步用的临时表目录；不存在或删不掉都不算失败。"""
    shutil.rmtree(path, ignore_errors=True)
