"""构造终末地索引测试用的最小游戏表；只写临时目录，不访问网络。

34 张表全部落盘（未用到的写成空对象），另加 maps.json 与 version 描述，
供 akedata_client.build_index 走真实代码路径。
"""

import json
from pathlib import Path

# 表里用 {"id": n} 引用的文案；text() 会查 I18nTextTable_CN。
I18N = {
    "1": "测试干员",
    "2": "测试武器",
    "3": "测试装备A",
    "4": "测试套装",
    "5": "测试关卡",
    "6": "测试敌人",
    "7": "测试活动",
    "8": "测试卡池",
    "9": "测试技能",
    "10": "测试天赋",
    "11": "测试潜能",
    "12": "后勤技能",
    "13": "测试装备B",
    "14": "套装效果",
    "15": "测试卡池类型",
}

MAPS = {
    "room_type_map": {"1": "制造站"},
    "ATTR_MAP": {"1": "生命值", "2": "攻击力", "39": "暴击率"},
    "ATTR_MAP_EN": {"1": "maxHp", "2": "atk", "94": "physicalResistance"},
    "param_type_map": {"1": "atk"},
    "profession_id_map": {"1": "近卫"},
    "weapon_id_map": {"1": "单手剑"},
    "char_type_map": {"1": "物理"},
    "MODIFIER_TYPE_MAP": {"5": "physicalResistance"},
    "COMPOSITE_NAME_MAP": {"Main": "主属性"},
    "DOMAIN_MAP": {"d1": "测试区域"},
}

VERSION = {"id": "test-1", "publishedAt": "2026-01-01T00:00:00+08:00", "tableCfgPath": "public/Json"}


def _skill_bundle(ranks: int = 12) -> list[dict]:
    return [
        {
            "blackboard": [{"key": "atk", "value": 1.5}],
            "coolDown": 10,
            "costValue": 20,
            "description": "造成{atk:0.0%}伤害",
            "skillName": {"id": 9},
            "subDescDataList": [{"name": {"id": 9}, "desc": f"{index}", "conditionId": ""}],
        }
        for index in range(ranks)
    ]


def _attribute_row(level: int = 90) -> dict:
    return {
        "Attribute": {
            "attrs": [
                {"attrType": 0, "attrValue": level},
                {"attrType": 1, "attrValue": 1000},
                {"attrType": 2, "attrValue": 100},
                {"attrType": 39, "attrValue": 10},
            ]
        }
    }


def base_tables() -> dict[str, dict]:
    """一套最小但自洽的表：一名 6★ 干员、一把专武、一套装备、一个关卡与一名敌人。"""
    return {
        "I18nTextTable_CN": I18N,
        "CharacterTable": {
            "chr_1": {
                "name": {"id": 1},
                "engName": "Tester",
                "rarity": 6,
                "profession": 1,
                "weaponType": 1,
                "charTypeId": "1",
                "mainAttrType": 1,
                "subAttrType": 2,
                "department": "测试部门",
                "attributes": [_attribute_row()],
            }
        },
        "CharGrowthTable": {
            "chr_1": {
                "skillGroupMap": {
                    "g1": {
                        "skillGroupType": 1,
                        "name": {"id": 9},
                        "desc": "造成{atk:0.0%}伤害",
                        "skillIdList": ["sk1"],
                        "icon": "skill_icon",
                    }
                },
                "talentNodeMap": {
                    "n1": {
                        "nodeType": 4,
                        "passiveSkillNodeInfo": {
                            "index": 1,
                            "level": 1,
                            "breakStage": 0,
                            "talentEffectId": "eff1",
                            "name": {"id": 10},
                        },
                    }
                },
            }
        },
        "CharacterPotentialTable": {
            "chr_1": {
                "potentialUnlockBundle": [
                    {"level": 1, "name": {"id": 11}, "potentialEffectId": "eff2"}
                ]
            }
        },
        "PotentialTalentEffectTable": {
            "eff1": {"desc": {"id": 10}, "dataList": [{"attrModifier": {"attrType": 2, "attrValue": 0.1}}]},
            "eff2": {"desc": {"id": 10}, "dataList": [{"attrModifier": {"attrType": 2, "attrValue": 0.2}}]},
        },
        "SkillPatchTable": {
            "sk1": {"SkillPatchDataBundle": _skill_bundle()},
            "sk2": {
                "SkillPatchDataBundle": [
                    {
                        "blackboard": [{"key": "atk", "value": 0.2}],
                        "description": "攻击力提高{atk:0.0%}",
                        "skillName": {"id": 14},
                    }
                ]
            },
        },
        "CharWpnRecommendTable": {"chr_1": {"weaponIds1": ["wpn_1"]}},
        "WeaponBasicTable": {
            "wpn_1": {
                "levelTemplateId": "t1",
                "rarity": 6,
                "weaponType": 1,
                "maxLv": 90,
                "weaponSkillList": ["sk2"],
                "engName": "TestWeapon",
            }
        },
        "WeaponUpgradeTemplateTable": {"t1": {"list": [{"baseAtk": 100}, {"baseAtk": 500}]}},
        "ItemTable": {
            "wpn_1": {"name": {"id": 2}, "iconId": "icon_wpn", "rarity": 6, "decoDesc": "武器说明"},
            "eq_1": {"name": {"id": 3}, "iconId": "icon_eq", "rarity": 5},
        },
        "EquipTable": {
            "eq_1": {
                "partType": 0,
                "minWearLv": 10,
                "domainId": "d1",
                "displayBaseAttrModifier": {"attrValue": 25.4},
                "displayAttrModifiers": [
                    {
                        "compositeAttr": "Main",
                        "attrType": 1,
                        "modifierType": 5,
                        "attrValue": 100,
                        "enhancedAttrValues": [100, 200],
                    },
                    {
                        "attrType": 39,
                        "modifierType": 6,
                        "attrValue": 0.1,
                        "enhancedAttrValues": [0.1, 0.2],
                    },
                ],
            }
        },
        "EquipSuitTable": {
            "set_1": {
                "list": [
                    {
                        "suitName": {"id": 4},
                        "skillID": "sk2",
                        "skillLv": 1,
                        "equipCnt": 3,
                    }
                ],
                "equipList": ["eq_1"],
            }
        },
        "DungeonTable": {
            "dun_1": {
                "dungeonName": {"id": 5},
                "dungeonCategory": "dungeon_highdifficulty",
                "dungeonPicPath": "dungeon_cover",
                "dungeonLevelDesc": {"id": 5},
                "recommendLv": 80,
                "sceneId": "scene1",
                "enemyIds": ["eny_1"],
                "enemyLevels": [80],
                "featureDesc": "关卡说明",
            }
        },
        "DungeonSeriesTable": {
            "ser_1": {
                "name": {"id": 5},
                "gameCategory": "dungeon_highdifficulty",
                "includeDungeonIds": ["dun_1"],
                "sortId": 1,
            }
        },
        "SeasonTowerTable": {},
        "SeasonTowerGameGroupTable": {
            "grp_1": {"stars": {"1": {"gameId": "dun_1"}}, "icon": "tower_icon"}
        },
        "SeasonTowerDungeonTable": {},
        "TimeRangeTable": {
            "time_a1": {
                "timeRangeList": [
                    {"openTime": "2026/01/01 04:00:00", "closeTime": "2026/02/01 03:59:59"}
                ]
            },
            "time_pool_1": {
                "timeRangeList": [
                    {"openTime": "2026/01/05 12:00:00", "closeTime": "2026/01/25 03:59:59"}
                ]
            },
            "time_version_v1d0": {
                "timeRangeList": [
                    {"openTime": "2026/01/01 04:00:00", "closeTime": "2026/02/05 03:59:59"}
                ]
            },
        },
        "EnemyTemplateDisplayInfoTable": {
            "eny_t1": {
                "name": {"id": 6},
                "description": "敌人描述",
                "displayType": 2,
                "abilityDescIds": ["ab1"],
                "templateId": "eny_t1",
            }
        },
        "EnemyTable": {"eny_1": {"templateId": "eny_t1", "attrTemplateId": "tpl_1", "bornBuffs": []}},
        "EnemyAttributeTemplateTable": {
            "tpl_1": {
                "levelIndependentAttributes": {"attrs": [{"attrType": 1, "attrValue": 100}]},
                "levelDependentAttributes": [
                    {
                        "attrs": [
                            {"attrType": 1, "attrValue": 1000},
                            {"attrType": 2, "attrValue": 50},
                            {"attrType": 20, "attrValue": 30},
                            {"attrType": 94, "attrValue": 10},
                        ]
                    }
                ]
                * 100,
            }
        },
        "EnemyAbilityDescTable": {"ab1": {"description": "特性说明"}},
        "SpaceshipCharSkillTable": {
            "chr_1": {"skillList": [{"skillId": "ss1", "unlockHint": {"id": 12}}]}
        },
        "SpaceshipSkillTable": {
            "ss1": {
                "talentName": {"id": 12},
                "roomType": 1,
                "icon": "logistics_icon",
                "skillNamePostfix": "α",
                "desc": "后勤说明",
            }
        },
        "ActivityTable": {
            "activity_test": {
                "name": {"id": 7},
                "timeId": "time_a1",
                "tabImg": "tab_a1",
                "tabImgColor": "#FFCC00",
            }
        },
        "GachaCharPoolTable": {
            "pool_1": {
                "name": {"id": 8},
                "type": 1,
                "upCharIds": ["chr_1"],
                "nameImage": "pool_1_1_1",
                "clientTopTimeId": "",
            }
        },
        "GachaWeaponPoolTable": {},
        "GachaCharPoolTypeTable": {},
        "GachaWeaponPoolTypeTable": {},
        "RewardTable": {},
        "BattlePassTaskTable": {},
        "BattlePassConditionTable": {},
        "ActivityWeeklyTaskTable": {},
        "ActivityWeeklyTaskMileStoneTable": {},
    }


def write_tables(directory: Path, overrides: dict | None = None) -> Path:
    """把表写进临时目录；overrides 用于制造缺字段或异常数据。"""
    tables = base_tables()
    tables.update(overrides or {})
    directory.mkdir(parents=True, exist_ok=True)
    for name, payload in tables.items():
        (directory / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    (directory / "maps.json").write_text(
        json.dumps(MAPS, ensure_ascii=False), encoding="utf-8"
    )
    return directory


def build_index(directory: Path, overrides: dict | None = None) -> dict:
    """写入临时表并构建索引（等价于同步时的 to_thread(build_index)）。"""
    from app.tools import akedata_client

    write_tables(directory, overrides)
    return akedata_client.build_index(directory, VERSION)


def minimal_index() -> dict:
    """不依赖任何表的极小索引，用于接口契约测试。"""
    return {
        "schema": 20,
        "version": "test-1",
        "published_at": VERSION["publishedAt"],
        "operators": {
            "chr_1": {
                "id": "chr_1",
                "name": "测试干员",
                "eng": "Tester",
                "rarity": 6,
                "profession": "近卫",
                "weapon_type": "单手剑",
                "element": "物理",
                "main_attr": "力量",
                "sub_attr": "敏捷",
                "department": "测试部门",
                "stats": [["生命值", 1000], ["攻击力", 100]],
                "skills": [
                    {
                        "type": "战技",
                        "name": "测试技能",
                        "desc": "造成伤害",
                        "forms": [],
                        "table": [{"label": "冷却时间（秒）", "values": ["10", "10", "10", "10"]}],
                        "icon": "skill_icon",
                    }
                ],
                "talents": [{"level": 1, "name": "测试天赋", "desc": "天赋说明"}],
                "potentials": [{"level": 1, "name": "测试潜能", "desc": "潜能说明"}],
                "logistics": [],
                "signature_weapon": "wpn_1",
                "recommended": ["wpn_1"],
            }
        },
        "weapons": {
            "wpn_1": {
                "id": "wpn_1",
                "name": "测试武器",
                "eng": "TestWeapon",
                "rarity": 6,
                "type": "单手剑",
                "max_atk": 500,
                "max_lv": 90,
                "icon": "icon_wpn",
                "deco": "武器说明",
                "owner": "测试干员",
                "skills": [{"name": "套装效果", "levels": ["攻击力提高20.0%"]}],
            }
        },
        "equip_sets": {
            "set_1": {
                "id": "set_1",
                "name": "测试套装",
                "count": 3,
                "effect": "攻击力提高",
                "rarity": 5,
                "level": 10,
                "domain": "测试区域",
                "pieces": [
                    {
                        "id": "eq_1",
                        "name": "测试装备A",
                        "part": "护甲",
                        "rarity": 5,
                        "level": 10,
                        "icon": "icon_eq",
                        "defense": 25,
                        "domain": "测试区域",
                        "attrs": [{"name": "生命值", "base": "100", "max": "200"}],
                    }
                ],
            }
        },
        "equip_items": {"测试装备A": {"icon": "icon_eq", "attrs": ["生命值"]}},
        "endgame": {"tower": {}, "tower_seasons": [], "monument": []},
        "leaders": [],
        "dungeons": [
            {
                "id": "dun_1",
                "name": "测试关卡",
                "base_name": "测试关卡",
                "level_desc": "",
                "category": "高难关卡",
                "recommend_lv": 80,
                "scene": "scene1",
                "levels": [80],
                "enemy_count": 1,
                "feature": "关卡说明",
            }
        ],
        "enemies": [
            {
                "id": "eny_t1",
                "name": "测试敌人",
                "desc": "敌人描述",
                "template": "eny_t1",
                "leader": True,
                "traits": ["特性说明"],
                "stats": {
                    "hp": 1000,
                    "atk": 50,
                    "def": 0,
                    "poise": 30,
                    "res": [["物理", 10]],
                },
            }
        ],
        "calendar": {
            "activities": [
                {
                    "id": "activity_test",
                    "name": "测试活动",
                    "open": "2026/01/01 04:00:00",
                    "close": "2026/02/01 03:59:59",
                    "tab": "tab_a1",
                    "color": "#FFCC00",
                }
            ],
            "pools": [
                {
                    "id": "pool_1",
                    "kind": "char",
                    "name": "测试卡池",
                    "up": ["测试干员"],
                    "open": "2026/01/05 12:00:00",
                    "close": "2026/01/25 03:59:59",
                }
            ],
            "passes": [],
            "weekly": {"name": "每周事务", "open": "", "weeks": {}, "milestones": []},
            "versions": [],
            "gifts": {},
        },
    }
