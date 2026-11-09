"""小黑盒（Heybox）终末地抽卡补录：转换校验与落库/撤销。"""

import json

import pytest

from app.core import gacha as gacha_core
from app.core.state import CommunityState
from app.models.config import SavedState
from app.models.gacha import GachaRecord
from app.tools import gacha_heybox as heybox

UID = "102819197"
BOX = "123456"
T0 = 1759291200  # 2025-10-01 12:00:00 +08:00
POOL_TYPE = "E_CharacterGachaPoolType_Special"


class _RecordingStore:
    """只记录落盘的假存储，不接触真实文件。"""

    def __init__(self) -> None:
        self.saves: list[SavedState] = []

    async def save_async(self, candidate: SavedState) -> None:
        self.saves.append(candidate)


@pytest.fixture
def temp_state() -> CommunityState:
    candidate = CommunityState()
    candidate.storage = _RecordingStore()
    candidate.data = SavedState()
    return candidate


def _pool(**overrides) -> dict:
    pool = {
        "pool_id": "special_1",
        "pool_name": "测试寻访",
        "records": [
            {"id": f"{UID}_special_6", "name": "陈千语", "timestamp": T0, "diff": 50}
        ],
        "free_records": [],
        "current_pity": 10,
        "total_count": 60,
    }
    pool.update(overrides)
    return pool


def _result(*, pools=None, **overrides) -> dict:
    result = {
        "is_bind": True,
        "user_info": {"uid": UID},
        "statistic_info": {"count_time": "2026-10-02 12:00:00"},
        "gacha_record": pools
        if pools is not None
        else [{"gacha_type": "special", "pool_records": [_pool()]}],
        "gacha_type_latest_seq_id": {POOL_TYPE: 60},
    }
    result.update(overrides)
    return result


def _payload(**kwargs) -> str:
    return json.dumps({"status": "ok", "result": _result(**kwargs)}, ensure_ascii=False)


def _official(record_id: str = "900", *, name: str = "陈千语", ts: int = T0) -> GachaRecord:
    return GachaRecord(
        game="endfield",
        playerUid=UID,
        id=record_id,
        poolType=POOL_TYPE,
        poolName="测试寻访",
        name=name,
        rarity=6,
        time="2025-10-01 12:00:00",
    )


def test_parse_overview_rejects_non_json_and_bad_status():
    with pytest.raises(heybox.HeyboxError) as plain:
        heybox.parse_overview("<html>登录</html>")
    assert "不是 JSON" in str(plain.value)

    with pytest.raises(heybox.HeyboxError) as status:
        heybox.parse_overview(json.dumps({"status": "failed"}))
    assert "状态不是 ok" in str(status.value)

    with pytest.raises(heybox.HeyboxError) as missing:
        heybox.parse_overview(json.dumps({"status": "ok", "result": {"user_info": {}}}))
    assert "缺少卡池记录" in str(missing.value)


def test_parse_overview_rejects_unbound_account():
    payload = json.dumps({"status": "ok", "result": _result(is_bind=False)})
    with pytest.raises(heybox.HeyboxError) as error:
        heybox.parse_overview(payload)
    assert "抽卡分析" in str(error.value)


def test_parse_overview_returns_result_for_bound_account():
    parsed = heybox.parse_overview(_payload())
    assert parsed["user_info"]["uid"] == UID


def test_records_require_valid_heybox_id():
    parsed = heybox.parse_overview(_payload())
    with pytest.raises(heybox.HeyboxError) as error:
        heybox.heybox_records(parsed, heybox_id="abc", uid=UID, official=[])
    assert "4-12 位数字" in str(error.value)


def test_records_require_matching_game_uid():
    parsed = heybox.parse_overview(_payload())
    with pytest.raises(heybox.HeyboxError) as error:
        heybox.heybox_records(parsed, heybox_id=BOX, uid="100000000", official=[])
    assert "不能导入别人的记录" in str(error.value)


def test_records_reject_foreign_uid_inside_pool():
    pool = _pool()
    pool["records"] = [dict(pool["records"][0], id="999000111_special_50")]
    parsed = heybox.parse_overview(_payload(pools=[{"gacha_type": "special", "pool_records": [pool]}]))
    with pytest.raises(heybox.HeyboxError) as error:
        heybox.heybox_records(parsed, heybox_id=BOX, uid=UID, official=[])
    assert "其他 UID" in str(error.value)


def test_records_reject_duplicate_identifiers():
    twin = {"id": f"{UID}_special_6", "name": "陈千语", "timestamp": T0, "diff": 1}
    pool = _pool(records=[twin, dict(twin)], current_pity=0, total_count=2)
    parsed = heybox.parse_overview(_payload(pools=[{"gacha_type": "special", "pool_records": [pool]}]))
    with pytest.raises(heybox.HeyboxError) as error:
        heybox.heybox_records(parsed, heybox_id=BOX, uid=UID, official=[])
    assert "重复的记录标识" in str(error.value)


def test_records_refuse_inconsistent_totals():
    pool = _pool(current_pity=3)
    parsed = heybox.parse_overview(_payload(pools=[{"gacha_type": "special", "pool_records": [pool]}]))
    with pytest.raises(heybox.HeyboxError) as error:
        heybox.heybox_records(parsed, heybox_id=BOX, uid=UID, official=[])
    assert "自身对不上" in str(error.value)


def test_records_build_placeholder_rows_and_keep_six_star_identity():
    parsed = heybox.parse_overview(_payload())
    records, warnings, skipped = heybox.heybox_records(
        parsed, heybox_id=BOX, uid=UID, official=[]
    )

    assert (warnings, skipped) == ([], [])
    assert len(records) == 60
    six = [item for item in records if item.rarity == 6]
    assert [item.name for item in six] == ["陈千语"]
    assert six[0].kind == heybox.KIND_SIX
    assert six[0].id == f"{UID}_special_6"
    assert not gacha_core.is_derived(six[0])
    fillers = [item for item in records if item.rarity == 4]
    assert len(fillers) == 59
    assert {item.name for item in fillers} == {heybox.PLACEHOLDER_NAME}
    assert {item.kind for item in fillers} == {heybox.KIND_FILL}
    assert all(gacha_core.is_derived(item) for item in fillers)
    assert len({item.id for item in records}) == 60
    assert all(item.poolType == POOL_TYPE for item in records)
    assert all(item.playerUid == UID and item.game == "endfield" for item in records)
    # 时间从旧到新：垫抽不晚于六星，六星之后才是末段垫抽。
    assert [item.time for item in records] == sorted(item.time for item in records)


def test_records_skip_rerun_and_unsupported_pools():
    rerun = _pool(pool_id="rerun_7", pool_name="重构寻访", current_pity=0, total_count=0)
    odd = _pool(pool_id="collab_9", pool_name="联动寻访", current_pity=0, total_count=0)
    parsed = heybox.parse_overview(
        _payload(
            pools=[
                {"gacha_type": "special", "pool_records": [rerun]},
                {"gacha_type": "special", "pool_records": [odd]},
            ]
        )
    )
    records, warnings, skipped = heybox.heybox_records(
        parsed, heybox_id=BOX, uid=UID, official=[]
    )

    assert records == []
    assert warnings == []
    assert len(skipped) == 2
    assert "重构寻访" in skipped[0]
    assert "暂不支持" in skipped[1]


def test_records_import_free_ten_pull_as_free_rows():
    free = {
        "id": f"{UID}_special_1",
        "name": "陈千语",
        "timestamp": T0,
        "diff": 3,
        "is_free": True,
    }
    pool = _pool(records=[], free_records=[free], current_pity=0, total_count=0)
    parsed = heybox.parse_overview(_payload(pools=[{"gacha_type": "special", "pool_records": [pool]}]))
    records, _, skipped = heybox.heybox_records(
        parsed, heybox_id=BOX, uid=UID, official=[]
    )

    assert skipped == []
    assert len(records) == 10
    assert all(item.isFree for item in records)
    assert records[2].rarity == 6 and records[2].name == "陈千语"
    assert [item.rarity for item in records].count(4) == 9


def test_records_refuse_when_snapshot_is_older_than_official():
    parsed = heybox.parse_overview(_payload())
    records, _, skipped = heybox.heybox_records(
        parsed, heybox_id=BOX, uid=UID, official=[_official("900")]
    )

    assert records == []
    assert skipped and "快照早于已有官方记录" in skipped[0]


def test_records_fill_tail_pity_after_known_six_star():
    parsed = heybox.parse_overview(_payload())
    records, _, skipped = heybox.heybox_records(
        parsed, heybox_id=BOX, uid=UID, official=[_official("60")]
    )

    assert skipped == []
    assert len(records) == 59  # 六星已在官方记录里，只补垫抽
    assert all(item.rarity == 4 for item in records)
    # 六星之前的 49 抽，加上它那一次十连里剩下的 3 个位置，都落在六星这一秒；
    # 之后的 current_pity=10 里剩 7 抽更晚。
    assert sum(1 for item in records if item.time <= "2025-10-01 12:00:00") == 52
    assert sum(1 for item in records if item.time > "2025-10-01 12:00:00") == 7


def test_records_refuse_when_six_stars_disagree_with_official():
    parsed = heybox.parse_overview(_payload())
    with pytest.raises(heybox.HeyboxError) as error:
        heybox.heybox_records(
            parsed, heybox_id=BOX, uid=UID, official=[_official("60", name="别人")]
        )
    assert "六星记录与已有官方记录对不上" in str(error.value)


@pytest.mark.asyncio
async def test_import_and_revoke_round_trip(temp_state, monkeypatch):
    monkeypatch.setattr(gacha_core, "state", temp_state)
    monkeypatch.setattr(gacha_core.endfield_wiki, "index", lambda: {})

    added, replaced, warnings, skipped = await gacha_core.import_heybox(
        "endfield", BOX, UID, _payload()
    )
    assert (added, replaced, warnings, skipped) == (60, 0, [], [])
    assert len(temp_state.data.gacha) == 60

    # 同一份数据再导一次：派生行整体替换、六星按 record_key 覆盖，一条都不能丢。
    added, replaced, _, _ = await gacha_core.import_heybox("endfield", BOX, UID, _payload())
    assert (added, replaced) == (0, 59)
    assert len(temp_state.data.gacha) == 60

    removed = await gacha_core.revoke_heybox(UID)
    assert removed == 59
    survivors = temp_state.data.gacha
    assert [item.name for item in survivors] == ["陈千语"]
    assert not any(gacha_core.is_derived(item) for item in survivors)


@pytest.mark.asyncio
async def test_import_rejects_other_games_and_leaves_data_untouched(temp_state, monkeypatch):
    monkeypatch.setattr(gacha_core, "state", temp_state)
    monkeypatch.setattr(gacha_core.endfield_wiki, "index", lambda: {})

    with pytest.raises(ValueError):
        await gacha_core.import_heybox("genshin", BOX, UID, _payload())

    bad = _payload()
    wrong_uid = json.dumps(
        {"status": "ok", "result": _result(user_info={"uid": "100000000"})},
        ensure_ascii=False,
    )
    with pytest.raises(heybox.HeyboxError):
        await gacha_core.import_heybox("endfield", BOX, UID, wrong_uid)
    assert temp_state.data.gacha == []
    assert bad  # 保留变量名，避免误删构造步骤


@pytest.mark.asyncio
async def test_revoke_only_touches_requested_uid(temp_state, monkeypatch):
    monkeypatch.setattr(gacha_core, "state", temp_state)
    other = GachaRecord(
        game="endfield",
        playerUid="100000000",
        id="heybox:123456:special_1:0",
        poolType=POOL_TYPE,
        poolName="测试寻访",
        name=heybox.PLACEHOLDER_NAME,
        rarity=4,
        time="2025-10-01 12:00:00",
    )
    mine = other.model_copy(update={"playerUid": UID})
    temp_state.data.gacha = [other, mine]

    removed = await gacha_core.revoke_heybox(UID)

    assert removed == 1
    assert [item.playerUid for item in temp_state.data.gacha] == ["100000000"]


@pytest.mark.asyncio
async def test_skipped_pools_preserve_previous_import(temp_state, monkeypatch):
    monkeypatch.setattr(gacha_core, "state", temp_state)
    await gacha_core.import_heybox("endfield", BOX, UID, _payload())
    original = temp_state.data.gacha.copy()
    unsupported = _payload(pools=[{
        "gacha_type": "special", "pool_records": [_pool(pool_id="rerun_1")],
    }])
    added, replaced, _, skipped = await gacha_core.import_heybox(
        "endfield", BOX, UID, unsupported
    )
    assert (added, replaced) == (0, 0)
    assert skipped
    assert temp_state.data.gacha == original


@pytest.mark.asyncio
async def test_huge_import_is_rejected_before_expansion_and_keeps_records(temp_state, monkeypatch):
    monkeypatch.setattr(gacha_core, "state", temp_state)
    temp_state.data.gacha = [_official("60")]
    pool = _pool(records=[], current_pity=10**12, total_count=10**12)
    payload = _payload(pools=[{"gacha_type": "special", "pool_records": [pool]}])
    with pytest.raises(heybox.HeyboxError, match="20 万条"):
        await gacha_core.import_heybox("endfield", BOX, UID, payload)
    assert temp_state.data.gacha == [_official("60")]
    assert temp_state.storage.saves == []


def test_import_limit_applies_across_pools(monkeypatch):
    monkeypatch.setattr(heybox, "MAX_IMPORT_RECORDS", 100)
    result = _result(pools=[{
        "gacha_type": "special",
        "pool_records": [_pool(), _pool(pool_id="special_2")],
    }])
    with pytest.raises(heybox.HeyboxError, match="20 万条"):
        heybox.heybox_records(result, heybox_id=BOX, uid=UID, official=[])


def test_free_ten_pulls_count_towards_import_limit(monkeypatch):
    monkeypatch.setattr(heybox, "MAX_IMPORT_RECORDS", 10)
    free = {"id": f"{UID}_special_2", "timestamp": T0, "is_free": True}
    pool = _pool(records=[], current_pity=0, total_count=0, free_records=[free, free])
    with pytest.raises(heybox.HeyboxError, match="20 万条"):
        heybox.heybox_records(
            _result(pools=[{"gacha_type": "special", "pool_records": [pool]}]),
            heybox_id=BOX, uid=UID, official=[],
        )


def test_huge_five_star_count_is_bounded_before_expansion():
    result = _result()
    entry = result["gacha_record"][0]["pool_records"][0]["records"][0]
    entry["sr_list"] = [{"name": "示例五星", "count": 10**12}]
    records, _, _ = heybox.heybox_records(result, heybox_id=BOX, uid=UID, official=[])
    assert len(records) == 60
    assert sum(item.rarity == 5 for item in records) == 49


@pytest.mark.asyncio
async def test_five_star_names_and_fillers_do_not_share_ids(temp_state, monkeypatch):
    monkeypatch.setattr(gacha_core, "state", temp_state)
    result = _result()
    entry = result["gacha_record"][0]["pool_records"][0]["records"][0]
    entry["sr_list"] = [{"name": "示例五星甲", "count": 10}, {"name": "示例五星乙", "count": 10}]
    payload = json.dumps({"status": "ok", "result": result})
    await gacha_core.import_heybox("endfield", BOX, UID, payload)
    first = temp_state.data.gacha.copy()
    assert len(first) == len({item.id for item in first}) == 60
    assert sum(item.rarity == 5 for item in first) == 20
    added, _, _, _ = await gacha_core.import_heybox("endfield", BOX, UID, payload)
    assert added == 0
    assert temp_state.data.gacha == first


@pytest.mark.parametrize("position,diff,pity", [(10**12, 50, 10), (6, -10, 70)])
def test_invalid_position_and_negative_intervals_are_rejected(position, diff, pity):
    result = _result()
    pool = result["gacha_record"][0]["pool_records"][0]
    pool["records"][0].update(id=f"{UID}_special_{position}", diff=diff)
    pool["current_pity"] = pity
    with pytest.raises(heybox.HeyboxError, match="无效"):
        heybox.heybox_records(result, heybox_id=BOX, uid=UID, official=[])

