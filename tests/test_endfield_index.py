"""索引构建、文本转换与版本差异的单元测试；只读临时目录，不访问网络。"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import endfield_fixtures as fixtures  # noqa: E402

from app.tools import akedata_client, endfield_changes  # noqa: E402


def test_tables_list_covers_34_akedata_tables():
    # 上游的下载清单是固定的 34 张表，移植时必须保持完整且不重复。
    assert len(akedata_client.TABLES) == 34
    assert len(set(akedata_client.TABLES)) == 34
    assert {"CharacterTable", "DungeonTable", "EnemyTable"} <= set(akedata_client.TABLES)


def test_build_index_from_minimal_tables(tmp_path):
    index = fixtures.build_index(tmp_path)
    assert index["schema"] == akedata_client.INDEX_SCHEMA
    assert index["version"] == fixtures.VERSION["id"]
    assert akedata_client.index_counts(index) == {
        "characters": 1,
        "weapons": 1,
        "equipSuits": 1,
        "dungeons": 1,
        "enemies": 1,
        "activities": 1,
    }


def test_build_index_operator_fields(tmp_path):
    operator = fixtures.build_index(tmp_path)["operators"]["chr_1"]
    assert operator["name"] == "测试干员"
    assert operator["rarity"] == 6
    assert operator["profession"] == "近卫"
    assert operator["signature_weapon"] == "wpn_1"
    assert ("生命值", 1000) in operator["stats"]
    # 占位符 {atk:0.0%} 用技能自身的黑板值 1.5 填入 150.0%。
    assert operator["skills"][0]["desc"] == "造成150.0%伤害"
    assert operator["talents"][0]["name"] == "测试天赋"
    assert operator["logistics"][0]["levels"][0]["postfix"] == "α"


def test_build_index_skill_level_table(tmp_path):
    table = fixtures.build_index(tmp_path)["operators"]["chr_1"]["skills"][0]["table"]
    labels = [row["label"] for row in table]
    assert "技力消耗" in labels and "冷却时间（秒）" in labels
    # 只保留最后四级。
    assert all(len(row["values"]) == 4 for row in table)


def test_build_index_weapon_and_equip_set(tmp_path):
    index = fixtures.build_index(tmp_path)
    weapon = index["weapons"]["wpn_1"]
    assert weapon["max_atk"] == 500
    assert weapon["owner"] == "测试干员"
    assert weapon["skills"][0]["levels"] == ["攻击力提高20.0%"]
    equip_set = index["equip_sets"]["set_1"]
    assert equip_set["name"] == "测试套装"
    assert equip_set["pieces"][0]["defense"] == 25
    # compositeAttr 为 Main 时用具名属性；modifierType 6 按百分比展示，5 是纯数值。
    attrs = {
        attr["name"]: (attr["base"], attr["max"])
        for attr in equip_set["pieces"][0]["attrs"]
    }
    assert attrs["主属性"] == ("100", "200")
    assert attrs["暴击率"] == ("10.0%", "20.0%")


def test_build_index_calendar_activities_and_pools(tmp_path):
    calendar = fixtures.build_index(tmp_path)["calendar"]
    assert calendar["activities"][0]["name"] == "测试活动"
    assert calendar["activities"][0]["open"] == "2026/01/01 04:00:00"
    assert calendar["pools"][0]["up"] == ["测试干员"]
    assert calendar["versions"][0]["name"] == "1.0"


def test_stage_enemies_without_spawner_files_are_marked_plain(tmp_path):
    index = fixtures.build_index(tmp_path)
    stats = akedata_client.stage_stats(index)
    assert stats["stages"] >= 1
    assert stats["foes_plain"] == stats["foes"]  # 没有 spawner 文件时全部为 plain


def test_rich_to_html_escapes_and_keeps_styles():
    converted = akedata_client.rich_to_html(
        "a<b & c <@vup>+10%</> <#term>词条</> <image src=x>"
    )
    assert "&lt;b &amp; c" in converted
    assert '<span class="up">+10%</span>' in converted
    assert '<span class="term">词条</span>' in converted
    assert "<image" not in converted  # 图片标记整段丢弃
    assert akedata_client.rich_to_html("第一行\n第二行").count("<br>") == 1


def test_fill_placeholders_leaves_unknown_values():
    assert akedata_client.fill_placeholders("{atk:0}", {"atk": 12.4}) == "12"
    assert akedata_client.fill_placeholders("{missing:0}", {}) == "?"
    assert akedata_client.fill_placeholders("没有占位符", {}) == "没有占位符"


def test_modifier_notes_follow_akedata_stacking():
    modifiers = [
        {"attrType": 1, "modifierType": 5, "attrValue": 100},
        {"attrType": 1, "modifierType": 6, "attrValue": 0.5},
        {"attrType": 1, "modifierType": 6, "attrValue": 0.2},
    ]
    notes = akedata_client.modifier_notes(modifiers, {1: "最大生命值"})
    # 百分比复合：1.5 * 1.2 - 1 = 80%。
    assert notes == ["最大生命值 +100", "最大生命值 +80%"]


def test_icon_urls_are_empty_without_ids():
    assert akedata_client.char_icon_url("").startswith("")
    assert akedata_client.char_icon_url("") == ""
    assert akedata_client.char_icon_url("chr_1").endswith("/charremoteicon/icon_chr_1.png")
    assert akedata_client.weapon_icon_url("icon_wpn").endswith("/itemiconbig/icon_wpn.png")
    assert akedata_client.equip_icon_url("icon_eq").endswith("/itemicon/icon_eq.png")
    assert akedata_client.enemy_icon_url("eny_1").endswith("/monstericonbig/eny_1.png")
    assert akedata_client.stage_cover_url({"mode": "战争回响", "cover": "c"}) != ""
    assert akedata_client.stage_cover_url({"mode": "影拓丰碑", "cover": ""}) == ""


def test_http_client_ignores_environment_proxy(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1/")
    client = akedata_client.http_client(proxy=None)
    try:
        assert client.trust_env is False
        assert client.follow_redirects is True
    finally:
        import asyncio

        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            client.aclose()
        )


def test_latest_version_prefers_manifest_pointer():
    manifest = {"latest": "b", "versions": [{"id": "a"}, {"id": "b"}]}
    assert akedata_client.latest_version(manifest)["id"] == "b"
    assert akedata_client.latest_version({"versions": [{"id": "a"}]})["id"] == "a"
    with pytest.raises(akedata_client.AkedataError):
        akedata_client.latest_version({"versions": []})


def test_changes_added_reports_new_names(tmp_path):
    index = fixtures.build_index(tmp_path)
    grown = json.loads(json.dumps(index))
    grown["operators"]["chr_2"] = {"name": "新干员"}
    added = endfield_changes.added(index, grown)
    assert added["干员"] == ["新干员"]
    assert endfield_changes.added(index, index) == {
        kind: [] for kind in endfield_changes.names(index)
    }
    assert "新增干员：新干员" in endfield_changes.notice_lines(added)


def test_changes_problems_reports_missing_texts(tmp_path):
    index = fixtures.build_index(tmp_path)
    assert endfield_changes.problems(index) == []
    broken = json.loads(json.dumps(index))
    broken["operators"]["chr_1"]["skills"][0]["desc"] = "造成{atk:0.0%}伤害"
    broken["weapons"]["wpn_1"]["skills"][0]["levels"] = [""]
    found = endfield_changes.problems(broken)
    assert any("没填上的数值" in item for item in found)
    assert any("没有说明" in item for item in found)


def test_changes_problems_reports_empty_categories():
    found = endfield_changes.problems({"operators": {}, "weapons": [], "dungeons": []})
    assert "索引里没有任何干员" in found
    assert "索引里没有任何武器" in found
    assert "索引里没有任何关卡" in found
