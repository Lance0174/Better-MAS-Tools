"""远端会话限流与来源还原测试：不启动服务、不读取真实密码。"""

import pytest

from app.services.access import RemoteAccess, RemoteSessions, resolve_peer

PASSWORD = "correct-horse-battery"


def _sessions() -> RemoteSessions:
    return RemoteSessions(RemoteAccess("https://community.example.com", PASSWORD))


def _recorder() -> tuple[list[float], object]:
    delays: list[float] = []

    async def sleep(delay: float) -> None:
        delays.append(delay)

    return delays, sleep


def test_resolve_peer_trusts_forward_headers_only_from_private_sources():
    # 公网直连：伪造的转发头不能改变限流来源。
    assert resolve_peer("8.8.8.8", {"cf-connecting-ip": "1.1.1.1"}) == "8.8.8.8"
    assert (
        resolve_peer("8.8.4.4", {"x-forwarded-for": "1.1.1.1, 10.0.0.1"})
        == "8.8.4.4"
    )
    # 反代/隧道来源：按真实客户端来源计数。
    assert resolve_peer("127.0.0.1", {"cf-connecting-ip": "1.1.1.1"}) == "1.1.1.1"
    assert (
        resolve_peer("10.1.2.3", {"x-forwarded-for": "198.51.100.7, 10.1.2.3"})
        == "198.51.100.7"
    )
    assert resolve_peer("127.0.0.1", {}) == "127.0.0.1"
    assert resolve_peer("unknown", {"cf-connecting-ip": "1.1.1.1"}) == "unknown"


@pytest.mark.asyncio
async def test_per_source_failure_limit_blocks_only_that_source():
    sessions = _sessions()
    _, sleep = _recorder()
    for _ in range(5):
        with pytest.raises(ValueError, match="访问密码不正确"):
            await sessions.login("wrong-password", "198.51.100.1", sleep=sleep)
    with pytest.raises(ValueError, match="尝试过多"):
        await sessions.login(PASSWORD, "198.51.100.1", sleep=sleep)

    # 另一个来源不被牵连：这正是反代同源聚合时的关键性质。
    key = await sessions.login(PASSWORD, "198.51.100.2", sleep=sleep)
    assert sessions.valid(key)


@pytest.mark.asyncio
async def test_global_failures_delay_instead_of_locking_everyone_out():
    sessions = _sessions()
    delays, sleep = _recorder()
    for index in range(12):
        with pytest.raises(ValueError, match="访问密码不正确"):
            await sessions.login("wrong-password", f"198.51.100.{index}", sleep=sleep)
    # 全局退避确实生效，但合法来源仍能登录。
    assert delays and delays[-1] > 0
    key = await sessions.login(PASSWORD, "203.0.113.50", sleep=sleep)
    assert sessions.valid(key)


@pytest.mark.asyncio
async def test_successful_login_clears_source_failures():
    sessions = _sessions()
    _, sleep = _recorder()
    with pytest.raises(ValueError, match="访问密码不正确"):
        await sessions.login("wrong-password", "198.51.100.3", sleep=sleep)
    key = await sessions.login(PASSWORD, "198.51.100.3", sleep=sleep)
    assert sessions.valid(key)
    assert sessions.failures == {}
