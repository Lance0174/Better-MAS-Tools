"""检索解析测试：精确、唯一前缀、模糊与同音字降级；不访问网络。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import endfield_fixtures as fixtures  # noqa: E402

from app.tools import endfield_lookup as lookup  # noqa: E402


@pytest.fixture()
def index(tmp_path):
    return fixtures.build_index(tmp_path)


@pytest.fixture()
def resolver(index):
    aliases = {
        "operators": {"测试干员": {"aliases": ["小测", "Tester"], "signature_weapon": "测试武器"}},
        "weapons": {"测试武器": ["测试刀"]},
    }
    return lookup.Resolver(index, aliases)


def test_normalize_strips_punctuation_and_case():
    assert lookup.normalize("J.E.T.") == "jet"
    assert lookup.normalize(" 黎诺 · 测试 ") == "黎诺测试"
    assert lookup.normalize("ＡＢＣ") == "abc"  # NFKC 全角转半角


def test_resolve_exact_name(resolver):
    found = resolver.resolve("测试干员")
    assert (found.kind, found.id) == ("operator", "chr_1")


def test_resolve_alias_and_english_name(resolver):
    assert resolver.resolve("小测").id == "chr_1"
    assert resolver.resolve("Tester").id == "chr_1"
    assert resolver.resolve("测试刀").id == "wpn_1"


def test_resolve_unique_prefix(resolver):
    found = resolver.resolve("测试干")
    assert (found.kind, found.id) == ("operator", "chr_1")


def test_resolve_ambiguous_prefix_lists_candidates():
    index = {
        "operators": {
            "chr_a": {"id": "chr_a", "name": "测试甲", "eng": "A"},
            "chr_b": {"id": "chr_b", "name": "测试乙", "eng": "B"},
        },
        "weapons": {},
        "equip_sets": {},
    }
    found = lookup.Resolver(index, {}).resolve("测试")
    assert found.kind == "candidates"
    assert sorted(found.candidates) == ["测试乙", "测试甲"]


def test_resolve_equip_piece_opens_its_set(resolver):
    found = resolver.resolve("测试装备A")
    assert (found.kind, found.id) == ("equip_set", "set_1")
    assert found.note == "测试装备A"


def test_resolve_signature_weapon_suffix(resolver):
    found = resolver.resolve("测试干员专武")
    assert (found.kind, found.id, found.owner) == ("weapon", "wpn_1", "chr_1")


def test_resolve_build_suffix_returns_operator(resolver):
    assert resolver.resolve("测试干员配装").id == "chr_1"


def test_resolve_unknown_and_empty_return_none(resolver):
    assert resolver.resolve("完全不存在的东西") is None
    assert resolver.resolve("   ") is None
    assert resolver.resolve("") is None


def test_fuzzy_match_corrects_a_typo():
    # 名字越长，difflib 的相似度越接近阈值；这里只差一字且唯一命中。
    index = {
        "operators": {"chr_a": {"id": "chr_a", "name": "测试干员阿尔法", "eng": "Alpha"}},
        "weapons": {},
        "equip_sets": {},
    }
    found = lookup.Resolver(index, {}).resolve("测试干员阿而法")
    assert found is not None and found.id == "chr_a"


def test_to_pinyin_without_pypinyin_returns_nothing(monkeypatch):
    monkeypatch.setattr(lookup, "pinyin", None)
    assert lookup.to_pinyin("测试干员") == set()
    # 常量只反映导入时的结果，不受运行时替换影响。
    assert lookup.HOMOPHONE_AVAILABLE == (lookup.pinyin is not None)


def test_lookup_degrades_without_pypinyin(resolver, monkeypatch):
    """没有 pypinyin 时同音字匹配关闭，精确、别名、前缀匹配照常可用。"""
    monkeypatch.setattr(lookup, "pinyin", None)
    assert resolver.resolve("测试干员").id == "chr_1"
    assert resolver.resolve("小测").id == "chr_1"
    assert resolver.resolve("测试干").id == "chr_1"
    assert resolver.resolve("测试干员专武").id == "wpn_1"
    assert resolver.resolve("测试武器").id == "wpn_1"


class _FakeStyle:
    NORMAL = 1


def _fake_pinyin(text, style=None, heteronym=True):
    """把测试用词按拼音逐字返回，用于验证同音字分支。"""
    table = {"黎诺": ["li", "nuo"], "梨诺": ["li", "nuo"], "测试": ["ce", "shi"]}
    return [[reading] for reading in table.get(text, [""])]


def test_homophone_match_with_injected_pinyin(monkeypatch):
    monkeypatch.setattr(lookup, "pinyin", _fake_pinyin)
    monkeypatch.setattr(lookup, "Style", _FakeStyle)
    assert lookup.to_pinyin("梨诺") == {"linuo"}
    index = {
        "operators": {"chr_x": {"id": "chr_x", "name": "梨诺", "eng": "Lino"}},
        "weapons": {},
        "equip_sets": {},
    }
    resolver = lookup.Resolver(index, {})
    found = resolver.resolve("黎诺")  # 同音不同字
    assert found is not None and (found.kind, found.id) == ("operator", "chr_x")


def test_load_aliases_reads_the_shipped_file():
    aliases = lookup.load_aliases()
    assert "operators" in aliases and aliases["operators"]
    assert lookup.load_aliases(Path("does-not-exist.json")) == {}
