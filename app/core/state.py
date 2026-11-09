"""独立账号与配置编排，写入成功后才发布内存状态。"""

import asyncio
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.models.config import AccountData, SavedState, SettingsData
from app.services.network import network
from app.services.storage import StateStorage, StateStore
from app.tools.community_sign_provider import (
    format_community_sign_results,
    get_community_sign_providers,
)
from app.utils.constants import UTC8
from app.utils.logger import get_logger

logger = get_logger("社区状态")


def normalize_account_uid(value: object) -> str | None:
    """把账号组标识归一为标准 UUID 字符串，无法解析时返回 None。

    账号组标识由 uuid4() 生成，标准形态是小写带连字符。前端或剪贴板可能
    回传大写、带花括号、带前后空白的写法；直接做字符串比较会把合法账号组
    误判成不存在（「账号组不存在」/「未找到指定的游戏社区账号组」）。
    """

    try:
        return str(UUID(str(value).strip()))
    except (AttributeError, TypeError, ValueError):
        return None


def match_account_uid(account_uids: Iterable[object], value: object) -> str | None:
    """在已知账号组键里查找与 value 等价的键，找不到返回 None。

    先按原值直接命中（兼容历史非 UUID 键），再按归一后的 UUID 比较，
    这样客户端回传大写或带花括号的标识也能命中真实账号组。
    """

    raw = str(value).strip() if value is not None else ""
    if not raw:
        return None
    keys = [str(uid) for uid in account_uids]
    if raw in keys:
        return raw
    normalized = normalize_account_uid(raw)
    if normalized is None:
        return None
    for key in keys:
        if key == normalized or normalize_account_uid(key) == normalized:
            return key
    return None


class CommunityAccount:
    """为迁出的社区协议保留小范围字段读写契约，不依赖 MAS ConfigBase。"""

    def __init__(self, owner: "CommunityState", uid: str):
        self.owner = owner
        self.uid = uid

    def get(self, section: str, name: str) -> object:
        if section != "GameSignAccount" or name not in AccountData.model_fields:
            raise KeyError(name)
        return getattr(self.owner.data.accounts[self.uid], name)

    async def set(self, section: str, name: str, value: object) -> bool:
        if section != "GameSignAccount" or name not in AccountData.model_fields:
            raise KeyError(name)
        if self.get(section, name) == value:
            return False
        await self.owner.update_account(self.uid, {name: value}, reset_date=False)
        return True

    async def _commit_changes(self) -> None:
        # 上游凭据轮换收尾会调用此接口；本项目先落盘后改内存，无脏内存问题。
        # 仍强制写一次，兼容"调用方先改内存再要求落盘"的旧流程。
        await self.owner.mutate(lambda _candidate: None, force=True)


class CommunityState:
    def __init__(self):
        self.data = SavedState()
        self.storage: StateStore | None = None
        self.lock = asyncio.Lock()
        self.revision = 0

    def initialize(self, directory: Path) -> None:
        self.storage = StateStorage(directory)
        self.data = self.storage.load()
        network.proxy = self.data.settings.Proxy or None

    @property
    def accounts(self) -> dict[str, CommunityAccount]:
        return {uid: CommunityAccount(self, uid) for uid in self.data.accounts}

    @property
    def proxy(self) -> str | None:
        return self.data.settings.Proxy or None

    def sign_results(self) -> dict[str, list[dict[str, object]]]:
        """补齐已启用但尚未执行的平台账号，避免局部成功被汇总为全部成功。"""
        configured = {}
        for uid, account in self.data.accounts.items():
            if not account.Enabled:
                continue
            for provider in get_community_sign_providers():
                credential = getattr(account, provider.token_field)
                if credential:
                    for platform in provider.resolve_platforms(credential):
                        configured[(uid, platform)] = account.Name
        grouped = format_community_sign_results(
            [
                item
                for item in self.data.results
                if (item.get("account_uid"), item.get("platform")) in configured
            ]
        )
        for (uid, platform), alias in configured.items():
            accounts = grouped.setdefault(platform, [])
            existing = next(
                (item for item in accounts if item["account_uid"] == uid), None
            )
            if existing is not None:
                existing["account_alias"] = alias
            else:
                accounts.append(
                    {"account_uid": uid, "account_alias": alias, "games": []}
                )
        return grouped

    async def mutate(
        self, change: Callable[[SavedState], None], *, force: bool = False
    ) -> None:
        async with self.lock:
            if self.storage is None:
                raise RuntimeError("配置存储尚未初始化")
            candidate = self.data.model_copy(deep=True)
            change(candidate)
            if not force and candidate == self.data:
                # 没有任何实际变更时不写盘、不推进 revision：凭据轮换收尾这类
                # 空提交否则会整份重写状态文件并让前端误以为数据变了。
                return
            writing = asyncio.create_task(self.storage.save_async(candidate))
            cancelled = False
            save_failed = False
            try:
                await asyncio.shield(writing)
            except asyncio.CancelledError:
                # 文件线程不会随请求取消；等待落盘再发布，避免下一次修改覆盖到旧状态。
                cancelled = True
                try:
                    await writing
                except Exception as error:
                    # 取消期间落盘失败：放弃本次修改（内存与磁盘仍是同一份旧状态），
                    # 但必须继续以 CancelledError 结束。否则普通异常会顶掉取消，
                    # asyncio.wait_for 的超时也会变成一次普通失败。
                    save_failed = True
                    logger.opt(exception=error).error("配置保存失败，本次修改已放弃")
            if save_failed:
                raise asyncio.CancelledError()
            self.data = candidate
            if self is state:
                # 只有全局状态代表本进程的代理设置。云端同步用临时 state 构造，
                # 默认 Proxy 为空，若照旧写入会把本地后端正在使用的代理清掉。
                network.proxy = candidate.settings.Proxy or None
            self.revision += 1
            if cancelled:
                raise asyncio.CancelledError()

    def match_account_uid(self, uid: object) -> str | None:
        """按归一后的 UUID 查找真实账号组键，找不到返回 None。"""

        return match_account_uid(self.data.accounts, uid)

    def require_account(self, uid: str) -> AccountData:
        key = self.match_account_uid(uid)
        if key is None:
            raise ValueError("账号组不存在")
        return self.data.accounts[key]

    async def create_account(self) -> str:
        uid = str(uuid4())
        await self.mutate(
            lambda candidate: candidate.accounts.update({uid: AccountData()})
        )
        return uid

    async def update_account(
        self, uid: str, fields: dict[str, object], *, reset_date: bool = True
    ) -> None:
        key = self.match_account_uid(uid)
        if key is None:
            raise ValueError("账号组不存在")

        def update(candidate: SavedState) -> None:
            previous = candidate.accounts[key].model_dump()
            changed = any(previous.get(key) != value for key, value in fields.items())
            if not changed:
                return
            previous.update(fields)
            if reset_date:
                previous["LastSignDate"] = ""
            candidate.accounts[key] = AccountData.model_validate(previous)

        await self.mutate(update)

    async def delete_account(self, uid: str) -> None:
        key = self.match_account_uid(uid)
        if key is None:
            raise ValueError("账号组不存在")

        def delete(candidate: SavedState) -> None:
            del candidate.accounts[key]
            candidate.results = [
                item for item in candidate.results if item.get("account_uid") != key
            ]

        await self.mutate(delete)

    async def reorder_accounts(self, order: list[str]) -> None:
        def reorder(candidate: SavedState) -> None:
            if len(order) != len(set(order)) or set(order) != set(candidate.accounts):
                raise ValueError("账号组排序必须包含全部账号且不得重复")
            candidate.accounts = {uid: candidate.accounts[uid] for uid in order}

        await self.mutate(reorder)

    async def update_settings(self, settings: SettingsData) -> None:
        def update(candidate: SavedState) -> None:
            # 旧客户端或尚未刷新的设置草稿不能把已跳过的引导重新打开。
            candidate.settings = settings.model_copy(
                update={
                    "OnboardingDismissed": (
                        candidate.settings.OnboardingDismissed
                        or settings.OnboardingDismissed
                    )
                }
            )

        await self.mutate(update)

    async def save_results(
        self, results: list[dict[str, object]], *, replace_accounts: bool = True
    ) -> None:
        affected = {item.get("account_uid") for item in results}
        keys = {
            (
                item.get("account_uid"),
                item.get("platform"),
                item.get("game"),
                item.get("account"),
            )
            for item in results
        }
        signed_at = datetime.now(tz=UTC8).isoformat(timespec="seconds")

        def merge(candidate: SavedState) -> None:
            candidate.results = [
                item
                for item in candidate.results
                if (
                    item.get("account_uid") not in affected
                    if replace_accounts
                    else (
                        item.get("account_uid"),
                        item.get("platform"),
                        item.get("game"),
                        item.get("account"),
                    )
                    not in keys
                )
            ] + [dict(item, signedAt=signed_at) for item in results]

        await self.mutate(merge)


state = CommunityState()
