"""日常便笺并发调度的取消语义：请求被取消时子任务必须一起取消并回收。"""

import asyncio

import pytest

from app.core import community_activity


class _Account:
    """只实现 _account_value 需要的字典式读取。"""

    def __init__(self) -> None:
        self._values = {
            "Enabled": True,
            "Name": "测试账号",
            "MiyousheDeviceId": "",
            "MiyousheDeviceFp": "",
        }

    def get(self, section: str, name: str, default: object = "") -> object:
        return self._values.get(name, default)


@pytest.mark.asyncio
async def test_cancelled_query_cancels_every_pending_platform(monkeypatch):
    cancelled = 0

    class _SlowProvider:
        def __init__(self, **_kwargs) -> None:
            pass

        async def discover_roles(self, **_kwargs):
            nonlocal cancelled
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled += 1
                raise
            raise AssertionError("角色发现不应在取消前返回")

    monkeypatch.setattr(
        community_activity, "CommunityActivityProvider", _SlowProvider
    )
    monkeypatch.setattr(
        community_activity, "_selected_accounts", lambda _ids: (("uid-1", _Account()),)
    )
    monkeypatch.setattr(
        "app.tools.community_sign_provider.get_community_token_field",
        lambda _platform: "Token",
    )
    monkeypatch.setattr(
        "app.tools.community_sign_provider.read_community_token",
        lambda _account, _field: "token",
    )

    before = len(asyncio.all_tasks())
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            community_activity.collect_configured_community_activity(), timeout=0.2
        )

    # 每个已登记平台各有一次角色发现；没有 finally 回收时它们会继续打上游。
    assert cancelled == len(community_activity.ACTIVITY_COMMUNITY_DEFINITIONS)
    assert len(asyncio.all_tasks()) == before
