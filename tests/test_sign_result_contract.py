"""签到成功判据集中化的回归测试。"""

from app.tools.community_contract import (
    COMMUNITY_SIGN_SUCCESS_STATUSES,
    is_community_sign_completed,
)
from app.tools.game_sign_result import merge_community_sign_result


def test_success_statuses_are_single_source():
    assert COMMUNITY_SIGN_SUCCESS_STATUSES == ("成功", "已签到")


def test_is_completed_accepts_status_and_underscore_flag():
    assert is_community_sign_completed({"status": "成功"})
    assert is_community_sign_completed({"status": "已签到"})
    # 状态串带空白时旧实现会判失败；归一后仍算完成。
    assert is_community_sign_completed({"status": " 成功 "})
    # 流程跑完但无法确认奖励：状态是失败，仍视为已完成。
    assert is_community_sign_completed({"status": "失败", "_completed": True})
    assert not is_community_sign_completed({"status": "失败"})
    assert not is_community_sign_completed({})


def test_merge_treats_padded_status_as_signed():
    merged = merge_community_sign_result(
        {"status": " 成功 ", "reason": ""},
        {"status": "已签到 ", "reason": ""},
    )

    assert merged["status"] == "成功"
    assert merged.get("reason", "") == ""
