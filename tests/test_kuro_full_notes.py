"""完整鸣潮便笺与部分数据降级，全部响应为合成数据。"""

import copy

import pytest

from app.tools import community_activity_provider as providers
from app.tools.community_activity_parser import parse_activity_snapshot
from app.tools.community_activity_transport import build_community_activity_requests
from tests.test_kuro_waves import WAVES_SAMPLE, _target


def sample():
    payload = copy.deepcopy(WAVES_SAMPLE)
    payload["data"].update(
        livenessData={"cur": 60, "total": 100},
        battlePassData=[{"name": "电台周经验", "cur": 500, "total": 10000}],
    )
    payload["_base_data"] = {
        "weeklyInstCount": 2,
        "weeklyInstCountLimit": 3,
        "storeEnergy": 60,
        "storeEnergyLimit": 480,
        "rougeScore": 300,
        "rougeScoreLimit": 1000,
    }
    return payload


def parse(payload):
    return parse_activity_snapshot(
        payload, account_uid="test", account_name="示例", platform="库街区", game="鸣潮"
    )


def test_full_notes_keep_daily_pass_stored_energy_and_remaining_weekly_attempts():
    snapshot = parse(sample())
    assert snapshot.status == "success"
    assert [
        (task["name"], task["completed"], task["target"])
        for task in snapshot.tasks
        if task.get("period", "daily") == "daily"
    ] == [("每日活跃度", 60, 100)]
    assert any(
        task["name"] == "电台周进度" and task["period"] == "weekly"
        for task in snapshot.tasks
    )
    weekly = next(task for task in snapshot.tasks if task["name"] == "周本剩余次数")
    assert weekly["completed"] == 0 and weekly["target"] == 0
    assert weekly["status"] == "剩余 2 / 3 次"
    assert any(
        resource["name"] == "结晶单质" and resource["current"] == 60
        for resource in snapshot.resources
    )


def test_small_widget_does_not_fake_missing_daily_data():
    snapshot = parse(copy.deepcopy(WAVES_SAMPLE))
    assert snapshot.tasks == ()
    assert "上游未返回每日活跃度、先约电台" in snapshot.reason


@pytest.mark.asyncio
async def test_detail_failure_keeps_daily_numbers_and_reports_partial_data(monkeypatch):
    calls = []

    async def request_json(_self, request, _call, **_kwargs):
        calls.append(request.source)
        if request.source.endswith("/baseData"):
            raise providers.CommunityActivityTransportError("详情暂不可用")
        return sample()

    monkeypatch.setattr(
        providers.CommunityActivityProvider, "_request_json", request_json
    )
    provider = providers.CommunityActivityProvider(
        platform="库街区", raw_credential='{"token":"offline"}'
    )
    payload = await provider.request(build_community_activity_requests(_target())[0])
    snapshot = parse(payload)
    assert snapshot.status == "success"
    assert any(task["name"] == "每日活跃度" for task in snapshot.tasks)
    assert "周本与结晶单质暂时未能获取" in snapshot.reason
    assert calls[-1].endswith("/baseData")
