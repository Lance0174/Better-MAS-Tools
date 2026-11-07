#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2024-2025 DLmaster361
#   Copyright © 2025-2026 AUTO-MAS Team

#   This file is part of AUTO-MAS.

#   AUTO-MAS is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.

#   AUTO-MAS is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
#   the GNU Affero General Public License for more details.

#   You should have received a copy of the GNU Affero General Public License
#   along with AUTO-MAS. If not, see <https://www.gnu.org/licenses/>.

#   Contact: DLmaster_361@163.com


"""游戏社区账号组到活动快照的核心消费层。"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from time import monotonic

from app.core.community_scheduler import community_activity_flow
from app.tools.community_activity_provider import CommunityActivityProvider
from app.tools.community_activity_roles import (
    ACTIVITY_COMMUNITY_DEFINITIONS,
    CommunityActivityProviderDefinition,
    CommunityActivityRole,
)
from app.tools.community_activity_transport import (
    CommunityActivityTarget,
    CommunityActivityTransportError,
    collect_community_activity,
)
from app.tools.community_contract import ActivityState, CommunityActivitySnapshot
from app.utils.constants import UTC8
from app.utils.logger import get_logger
from app.utils.security import format_exception_reason

__all__ = [
    "collect_configured_community_activity",
    "query_configured_community_activity",
    "reset_activity_cache",
]


logger = get_logger("游戏社区活动")

# 前端每次进入便笺页、切换账号筛选都会整份查询，命中缓存就不再打上游。
# 成功结果留 5 分钟，失败/受限结果只留 30 秒：既不让一次风控冷却被自己
# 反复触发，也不至于让用户看不到刚恢复的数据。
_ACTIVITY_CACHE_SECONDS = 300.0
_ACTIVITY_RETRY_SECONDS = 30.0
_SUCCESS_STATES = frozenset({"success", "empty"})


@dataclass(frozen=True)
class _ActivityCacheEntry:
    snapshots: tuple[CommunityActivitySnapshot, ...]
    expires_at: float


# 键是本机状态版本：配置一旦改动 state.revision 就变，旧快照自然不再命中。
_activity_cache: dict[tuple[int, str], _ActivityCacheEntry] = {}
_activity_cache_revision: int | None = None


def _cache_for(revision: int) -> dict[tuple[int, str], _ActivityCacheEntry]:
    """状态版本变化时整表丢弃，避免配置改动后继续复用旧快照。"""

    global _activity_cache, _activity_cache_revision
    if _activity_cache_revision != revision:
        _activity_cache = {}
        _activity_cache_revision = revision
    return _activity_cache


def reset_activity_cache() -> None:
    """清空便笺缓存；测试与重置配置时使用。"""

    global _activity_cache, _activity_cache_revision
    _activity_cache = {}
    _activity_cache_revision = None


def _account_value(account: object, name: str, default: object = "") -> object:
    try:
        return account.get("GameSignAccount", name)  # type: ignore[attr-defined]
    except (AttributeError, KeyError):
        return default


def _failure_state(error: Exception) -> tuple[ActivityState, str]:
    if isinstance(error, CommunityActivityTransportError):
        return error.status, error.reason
    if isinstance(error, ValueError):
        text = str(error)
        if any(marker in text for marker in ("风控", "限制", "非 JSON")):
            return "limited", "社区角色列表受到上游限制"
        return "unavailable", "社区角色列表响应无法识别"
    return "failed", "社区角色列表请求失败"


def _merge_reason(reason: str, note: str) -> str:
    """把发现阶段的提示追到已有说明后面，不顶掉解析器自己写的原因。"""

    base = str(reason or "").strip()
    extra = str(note or "").strip()
    if not extra:
        return base
    return f"{base}；{extra}" if base else extra


def _empty_game_snapshot(
    *,
    account_uid: str,
    account_name: str,
    definition: CommunityActivityProviderDefinition,
    game: str,
    status: ActivityState = "empty",
    reason: str = "未发现已绑定角色",
    role: CommunityActivityRole | None = None,
) -> CommunityActivitySnapshot:
    return CommunityActivitySnapshot(
        account=account_name,
        account_uid=account_uid,
        game=game,
        platform=definition.platform,
        status=status,
        reason=reason,
        updated_at=datetime.now(tz=UTC8).isoformat(),
        role_name=role.role_name if role is not None else "",
        role_uid=role.role_uid if role is not None else "",
        server=role.server if role is not None else "",
    )


def _targets_for_roles(
    *,
    roles: Sequence[CommunityActivityRole],
    account_uid: str,
    account_name: str,
    miyoushe_device_id: str = "",
    miyoushe_device_fp: str = "",
) -> tuple[CommunityActivityTarget, ...]:
    return tuple(
        role.to_target(
            account_uid=account_uid,
            account_name=account_name,
            device_id=(
                miyoushe_device_id
                if role.platform == "米游社" and role.game == "绝区零"
                else ""
            ),
            device_fp=(
                miyoushe_device_fp
                if role.platform == "米游社" and role.game == "绝区零"
                else ""
            ),
        )
        for role in roles
    )


def _selected_accounts(
    account_ids: Sequence[str] | None,
) -> tuple[tuple[str, object], ...]:
    from app.core.state import match_account_uid, state

    requested_ids = [
        str(account_id).strip()
        for account_id in (account_ids or ())
        if str(account_id or "").strip()
    ]
    accounts = state.accounts
    if not requested_ids:
        return tuple((str(uid), account) for uid, account in accounts.items())
    # 账号组标识按 UUID 归一再比较：客户端回传大写或带花括号的写法时，
    # 裸字符串比较会误报「未找到指定的游戏社区账号组」。
    resolved: list[str] = []
    for requested in requested_ids:
        key = match_account_uid(accounts, requested)
        if key is None:
            raise ValueError("未找到指定的游戏社区账号组")
        if key not in resolved:
            resolved.append(key)
    return tuple((key, accounts[key]) for key in resolved)


async def collect_configured_community_activity(
    account_ids: Sequence[str] | None = None,
    *,
    proxy: str | None = None,
    max_concurrency: int = 4,
) -> tuple[CommunityActivitySnapshot, ...]:
    """读取已配置账号组并查询已登记社区的日常活动。

    discover 与查询按"账号 × 平台"并发调度（semaphore 限流），避免平台间
    串行等待上游；顺序按账号 → 平台固定，保证前端展示稳定。
    """

    from app.core.state import state
    from app.tools.community_sign_provider import (
        get_community_token_field,
        read_community_token,
    )

    resolved_proxy = proxy if proxy is not None else state.proxy
    snapshots: list[CommunityActivitySnapshot] = []
    semaphore = asyncio.Semaphore(max_concurrency)

    async def query_one(
        account_uid: str,
        account: object,
        account_name: str,
        definition: CommunityActivityProviderDefinition,
        miyoushe_device_id: str,
        miyoushe_device_fp: str,
    ) -> list[CommunityActivitySnapshot]:
        token_field = get_community_token_field(definition.platform)
        try:
            token = read_community_token(account, token_field)
        except Exception:
            return list(
                _empty_game_snapshot(
                    account_uid=account_uid,
                    account_name=account_name,
                    definition=definition,
                    game=game,
                    status="failed",
                    reason="社区凭据无法读取",
                )
                for game in definition.games
            )
        if not token:
            return []

        async with semaphore:
            provider = CommunityActivityProvider(
                platform=definition.platform,
                raw_credential=token,
                proxy=resolved_proxy,
            )
            try:
                discovered = await provider.discover_roles(
                    account_uid=account_uid,
                    account_name=account_name,
                )
            except Exception as error:
                status, reason = _failure_state(error)
                logger.warning(f"{account_name} {definition.platform}角色发现失败: {reason}")
                return list(
                    _empty_game_snapshot(
                        account_uid=account_uid,
                        account_name=account_name,
                        definition=definition,
                        game=game,
                        status=status,
                        reason=reason,
                    )
                    for game in definition.games
                )

            capability = discovered.activity_capability
            if capability.status == "limited":
                limited: list[CommunityActivitySnapshot] = []
                for game in definition.games:
                    game_roles = discovered.roles_for_game(game)
                    if game_roles:
                        limited.extend(
                            _empty_game_snapshot(
                                account_uid=account_uid,
                                account_name=account_name,
                                definition=definition,
                                game=game,
                                status="limited",
                                reason=capability.reason,
                                role=role,
                            )
                            for role in game_roles
                        )
                    else:
                        limited.append(
                            _empty_game_snapshot(
                                account_uid=account_uid,
                                account_name=account_name,
                                definition=definition,
                                game=game,
                            )
                        )
                return limited

            targets = _targets_for_roles(
                roles=discovered.roles,
                account_uid=account_uid,
                account_name=account_name,
                miyoushe_device_id=miyoushe_device_id,
                miyoushe_device_fp=miyoushe_device_fp,
            )
            queried: tuple[CommunityActivitySnapshot, ...] = ()
            if targets:
                queried = await collect_community_activity(
                    targets,
                    provider.request,
                    max_concurrency=max_concurrency,
                )

            # ready 状态下的 capability.reason 是发现阶段留下的提示（例如角色列表
            # 没读全）。卡片本身是真实数据，所以不降级状态，只在 reason 里补一句。
            capability_note = capability.reason.strip()
            game_snapshots: list[CommunityActivitySnapshot] = []
            for game in definition.games:
                game_roles = tuple(
                    snapshot for snapshot in queried if snapshot.game == game
                )
                if game_roles:
                    game_snapshots.extend(
                        replace(
                            snapshot,
                            reason=_merge_reason(snapshot.reason, capability_note),
                        )
                        if capability_note
                        else snapshot
                        for snapshot in game_roles
                    )
                else:
                    game_snapshots.append(
                        _empty_game_snapshot(
                            account_uid=account_uid,
                            account_name=account_name,
                            definition=definition,
                            game=game,
                        )
                    )
            return game_snapshots

    tasks: list[tuple[int, int, asyncio.Task[list[CommunityActivitySnapshot]]]] = []
    selected = _selected_accounts(account_ids)
    for account_index, (account_uid, account) in enumerate(selected):
        account_name = str(_account_value(account, "Name", "用户") or "用户")
        if not _account_value(account, "Enabled", False):
            continue
        try:
            miyoushe_device_id = str(
                _account_value(account, "MiyousheDeviceId", "") or ""
            ).strip()
            miyoushe_device_fp = str(
                _account_value(account, "MiyousheDeviceFp", "") or ""
            ).strip()
        except Exception:
            # 设备字段读取失败只限制绝区零便笺，不影响同账号的其他游戏。
            miyoushe_device_id = ""
            miyoushe_device_fp = ""

        for definition_index, definition in enumerate(ACTIVITY_COMMUNITY_DEFINITIONS):
            task = asyncio.create_task(
                query_one(
                    account_uid,
                    account,
                    account_name,
                    definition,
                    miyoushe_device_id,
                    miyoushe_device_fp,
                )
            )
            tasks.append((account_index, definition_index, task))

    try:
        for account_index, definition_index, task in tasks:
            try:
                snapshots.extend(await task)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                # 单个平台查询异常不应拖垮整个面板；补齐该平台的空结果。
                definition = ACTIVITY_COMMUNITY_DEFINITIONS[definition_index]
                account_uid, account = selected[account_index]
                account_name = str(_account_value(account, "Name", "用户") or "用户")
                _, reason = _failure_state(error)
                logger.warning(
                    f"{account_name} {definition.platform}活动查询失败: {reason}"
                )
                snapshots.extend(
                    _empty_game_snapshot(
                        account_uid=account_uid,
                        account_name=account_name,
                        definition=definition,
                        game=game,
                        status="failed",
                        reason=reason,
                    )
                    for game in definition.games
                )
    finally:
        # 请求被取消或提前失败时，剩余任务必须取消并回收：否则它们会继续
        # 打上游，且没人 await 的异常只会在事件循环里变成噪声。
        pending = [task for _, _, task in tasks if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    return tuple(snapshots)


def _account_failure_snapshots(
    account_ids: Sequence[str], error: Exception
) -> tuple[CommunityActivitySnapshot, ...]:
    """整批查询异常时补齐每个账号 × 平台的可读状态，面板不至于整页空白。"""

    status, reason = _failure_state(error)
    names = {
        str(uid): str(_account_value(account, "Name", "用户") or "用户")
        for uid, account in _selected_accounts(None)
    }
    return tuple(
        _empty_game_snapshot(
            account_uid=str(uid),
            account_name=names.get(str(uid), "用户"),
            definition=definition,
            game=game,
            status=status,
            reason=reason,
        )
        for uid in account_ids
        for definition in ACTIVITY_COMMUNITY_DEFINITIONS
        for game in definition.games
    )


def _order_by_selection(
    selected: Sequence[tuple[str, object]],
    results: dict[str, tuple[CommunityActivitySnapshot, ...]],
) -> tuple[CommunityActivitySnapshot, ...]:
    """按账号 → 平台的固定顺序拼回结果，保证前端列表不随缓存命中顺序跳动。"""

    return tuple(item for uid, _account in selected for item in results.get(uid, ()))


async def query_configured_community_activity(
    account_ids: Sequence[str] | None = None,
    *,
    proxy: str | None = None,
    max_concurrency: int = 4,
    refresh: bool = False,
) -> tuple[CommunityActivitySnapshot, ...]:
    """查询便笺快照，命中缓存时不再访问上游。

    便笺页每次进入都会整份查询，直接调用 `collect_configured_community_activity`
    会让反复切页变成反复全量请求（还容易自己把风控冷却续上）。这里按账号缓存
    快照：命中就返回，未命中才补查；并发调用由调度锁串行化后复用同一份缓存。
    查询期间账号或设置被改（state.revision 变化）时丢弃这一轮结果，避免旧配置
    的响应被当作新配置缓存下来。
    """

    from app.core.state import state

    if not state.data.settings.ActivityEnabled:
        return ()

    async with community_activity_flow():
        for attempt in range(3):
            revision = state.revision
            cache = _cache_for(revision)
            selected = _selected_accounts(account_ids)
            if refresh:
                # 用户点「刷新」时清掉本次涉及的账号，其余账号继续复用缓存。
                for uid, _account in selected:
                    cache.pop((revision, uid), None)
            moment = monotonic()
            results: dict[str, tuple[CommunityActivitySnapshot, ...]] = {}
            missing: list[str] = []
            for uid, _account in selected:
                entry = cache.get((revision, uid))
                if entry is not None and moment < entry.expires_at:
                    results[uid] = entry.snapshots
                else:
                    missing.append(uid)
            if not missing:
                return _order_by_selection(selected, results)

            try:
                snapshots = await collect_configured_community_activity(
                    missing, proxy=proxy, max_concurrency=max_concurrency
                )
            except ValueError:
                raise
            except Exception as error:
                if state.revision != revision:
                    continue
                logger.warning(
                    format_exception_reason(
                        error, stage="游戏社区日常查询失败", include_message=False
                    )
                )
                snapshots = _account_failure_snapshots(missing, error)
                if not snapshots:
                    raise

            if state.revision != revision:
                # 等待上游期间配置变了：这批结果属于旧配置，不能写进缓存。
                if attempt == 2:
                    return snapshots
                continue

            completed = monotonic()
            grouped: dict[str, list[CommunityActivitySnapshot]] = {
                uid: [] for uid in missing
            }
            for item in snapshots:
                grouped.setdefault(item.account_uid, []).append(item)
            for uid, items in grouped.items():
                if not items:
                    continue
                ttl = (
                    _ACTIVITY_CACHE_SECONDS
                    if all(item.status in _SUCCESS_STATES for item in items)
                    else _ACTIVITY_RETRY_SECONDS
                )
                results[uid] = tuple(items)
                cache[(revision, uid)] = _ActivityCacheEntry(
                    snapshots=results[uid], expires_at=completed + ttl
                )
            return _order_by_selection(selected, results)

    # 连续三轮都在查询期间被改动：返回最后一次真实结果但不缓存。
    return await collect_configured_community_activity(
        account_ids, proxy=proxy, max_concurrency=max_concurrency
    )

