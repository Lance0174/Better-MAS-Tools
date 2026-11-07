"""便笺查询缓存：反复切页不再反复全量查询上游。

对照上游 AUTO-MAS d22e4d7c1（#1561）的语义：成功结果留 5 分钟、失败或受限
结果留 30 秒，配置变动立即失效，并发查询等待后只补查未命中账号。
"""

import asyncio

import pytest

from app.core import community_activity as core
from app.core import community_scheduler
from app.tools.community_contract import CommunityActivitySnapshot


class _Settings:
    def __init__(self, enabled: bool = True) -> None:
        self.ActivityEnabled = enabled


class _Data:
    def __init__(self, enabled: bool = True) -> None:
        self.settings = _Settings(enabled)


class _State:
    """只实现查询需要的三件事：账号表、开关、状态版本号。"""

    def __init__(self, accounts: dict | None = None, enabled: bool = True) -> None:
        self.data = _Data(enabled)
        self.accounts = accounts if accounts is not None else {"uid-1": object()}
        self.revision = 1


def _snapshot(uid: str = "uid-1", status: str = "success") -> CommunityActivitySnapshot:
    return CommunityActivitySnapshot(
        account="测试账号",
        account_uid=uid,
        game="鸣潮",
        platform="库街区",
        status=status,  # type: ignore[arg-type]
        updated_at="2026-11-05T20:00:00+08:00",
    )


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    core.reset_activity_cache()
    # 调度锁绑定事件循环：每个用例换一个循环，必须换新锁。
    monkeypatch.setattr(community_scheduler, "_community_activity_lock", asyncio.Lock())
    yield
    core.reset_activity_cache()


def _install(monkeypatch, state: _State, collect) -> list[tuple]:
    calls: list[tuple] = []

    async def fake_collect(account_ids=None, **_kwargs):
        calls.append(tuple(account_ids or ()))
        return await collect(account_ids)

    monkeypatch.setattr("app.core.state.state", state)
    monkeypatch.setattr(core, "collect_configured_community_activity", fake_collect)
    return calls


@pytest.mark.asyncio
async def test_second_query_hits_cache(monkeypatch):
    state = _State()

    async def collect(_ids):
        return (_snapshot(),)

    calls = _install(monkeypatch, state, collect)

    first = await core.query_configured_community_activity()
    second = await core.query_configured_community_activity()

    assert first == second
    assert calls == [("uid-1",)]


@pytest.mark.asyncio
async def test_failed_result_cools_down_for_thirty_seconds(monkeypatch):
    state = _State()

    async def collect(_ids):
        return (_snapshot(status="failed"),)

    calls = _install(monkeypatch, state, collect)
    moment = [1000.0]
    monkeypatch.setattr(core, "monotonic", lambda: moment[0])

    await core.query_configured_community_activity()
    moment[0] += 29.0
    await core.query_configured_community_activity()
    assert calls == [("uid-1",)]

    moment[0] += 2.0
    await core.query_configured_community_activity()
    assert calls == [("uid-1",), ("uid-1",)]


@pytest.mark.asyncio
async def test_success_result_survives_five_minutes(monkeypatch):
    state = _State()

    async def collect(_ids):
        return (_snapshot(),)

    calls = _install(monkeypatch, state, collect)
    moment = [1000.0]
    monkeypatch.setattr(core, "monotonic", lambda: moment[0])

    await core.query_configured_community_activity()
    moment[0] += 299.0
    await core.query_configured_community_activity()
    assert calls == [("uid-1",)]

    moment[0] += 2.0
    await core.query_configured_community_activity()
    assert calls == [("uid-1",), ("uid-1",)]


@pytest.mark.asyncio
async def test_config_change_invalidates_cache(monkeypatch):
    state = _State()

    async def collect(_ids):
        return (_snapshot(),)

    calls = _install(monkeypatch, state, collect)

    await core.query_configured_community_activity()
    state.revision += 1
    await core.query_configured_community_activity()

    assert calls == [("uid-1",), ("uid-1",)]


@pytest.mark.asyncio
async def test_disabled_activity_never_touches_upstream(monkeypatch):
    state = _State(enabled=False)

    async def collect(_ids):
        raise AssertionError("开关关闭时不应查询上游")

    calls = _install(monkeypatch, state, collect)

    assert await core.query_configured_community_activity() == ()
    assert calls == []


@pytest.mark.asyncio
async def test_concurrent_queries_only_hit_upstream_once(monkeypatch):
    state = _State()

    async def collect(_ids):
        await asyncio.sleep(0.05)
        return (_snapshot(),)

    calls = _install(monkeypatch, state, collect)

    results = await asyncio.gather(
        core.query_configured_community_activity(),
        core.query_configured_community_activity(),
    )

    assert results[0] == results[1]
    assert calls == [("uid-1",)]


@pytest.mark.asyncio
async def test_manual_refresh_bypasses_cache(monkeypatch):
    state = _State()

    async def collect(_ids):
        return (_snapshot(),)

    calls = _install(monkeypatch, state, collect)

    await core.query_configured_community_activity()
    await core.query_configured_community_activity(refresh=True)

    assert calls == [("uid-1",), ("uid-1",)]


@pytest.mark.asyncio
async def test_partial_accounts_only_query_missing(monkeypatch):
    state = _State({"uid-1": object(), "uid-2": object()})

    async def collect(ids):
        return tuple(_snapshot(uid) for uid in ids)

    calls = _install(monkeypatch, state, collect)

    await core.query_configured_community_activity(["uid-1"])
    await core.query_configured_community_activity(["uid-1", "uid-2"])

    assert calls == [("uid-1",), ("uid-2",)]


@pytest.mark.asyncio
async def test_unknown_account_raises_value_error(monkeypatch):
    state = _State()

    async def collect(_ids):
        raise AssertionError("未知账号不应触发查询")

    calls = _install(monkeypatch, state, collect)

    with pytest.raises(ValueError):
        await core.query_configured_community_activity(["uid-missing"])
    assert calls == []


@pytest.mark.asyncio
async def test_query_failure_reports_readable_state(monkeypatch):
    state = _State()

    async def collect(_ids):
        raise RuntimeError("boom")

    calls = _install(monkeypatch, state, collect)

    snapshots = await core.query_configured_community_activity()

    assert snapshots
    assert all(item.status == "failed" for item in snapshots)
    # 失败结果同样进缓存，避免每次切页都重打上游。
    await core.query_configured_community_activity()
    assert calls == [("uid-1",)]


@pytest.mark.asyncio
async def test_result_computed_under_old_config_is_not_reused(monkeypatch):
    state = _State()
    bumped = False

    async def collect(_ids):
        nonlocal bumped
        if not bumped:
            # 模拟等待上游期间用户改了账号：这一轮结果属于旧配置。
            bumped = True
            state.revision += 1
        return (_snapshot(),)

    calls = _install(monkeypatch, state, collect)

    first = await core.query_configured_community_activity()
    second = await core.query_configured_community_activity()

    # 旧配置结果被丢弃并重查一次；重查结果按新版本入缓存，后续调用不再请求。
    assert first == second
    assert calls == [("uid-1",), ("uid-1",)]
