"""独立账号与配置编排，写入成功后才发布内存状态。"""

import asyncio
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.models.config import AccountData, SavedState, SettingsData
from app.services.network import network
from app.services.storage import StateStorage, StateStore
from app.tools.community_sign_provider import (
    format_community_sign_results,
    get_community_sign_providers,
)
from app.utils.constants import UTC8


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
        await self.owner.mutate(lambda _candidate: None)


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

    async def mutate(self, change: Callable[[SavedState], None]) -> None:
        async with self.lock:
            if self.storage is None:
                raise RuntimeError("配置存储尚未初始化")
            candidate = self.data.model_copy(deep=True)
            change(candidate)
            writing = asyncio.create_task(self.storage.save_async(candidate))
            cancelled = False
            try:
                await asyncio.shield(writing)
            except asyncio.CancelledError:
                # 文件线程不会随请求取消；等待落盘再发布，避免下一次修改覆盖到旧状态。
                cancelled = True
                await writing
            self.data = candidate
            network.proxy = candidate.settings.Proxy or None
            self.revision += 1
            if cancelled:
                raise asyncio.CancelledError()

    def require_account(self, uid: str) -> AccountData:
        if uid not in self.data.accounts:
            raise ValueError("账号组不存在")
        return self.data.accounts[uid]

    async def create_account(self) -> str:
        uid = str(uuid4())
        await self.mutate(
            lambda candidate: candidate.accounts.update({uid: AccountData()})
        )
        return uid

    async def update_account(
        self, uid: str, fields: dict[str, object], *, reset_date: bool = True
    ) -> None:
        self.require_account(uid)

        def update(candidate: SavedState) -> None:
            previous = candidate.accounts[uid].model_dump()
            changed = any(previous.get(key) != value for key, value in fields.items())
            if not changed:
                return
            previous.update(fields)
            if reset_date:
                previous["LastSignDate"] = ""
            candidate.accounts[uid] = AccountData.model_validate(previous)

        await self.mutate(update)

    async def delete_account(self, uid: str) -> None:
        self.require_account(uid)

        def delete(candidate: SavedState) -> None:
            del candidate.accounts[uid]
            candidate.results = [
                item for item in candidate.results if item.get("account_uid") != uid
            ]

        await self.mutate(delete)

    async def reorder_accounts(self, order: list[str]) -> None:
        def reorder(candidate: SavedState) -> None:
            if len(order) != len(set(order)) or set(order) != set(candidate.accounts):
                raise ValueError("账号组排序必须包含全部账号且不得重复")
            candidate.accounts = {uid: candidate.accounts[uid] for uid in order}

        await self.mutate(reorder)

    async def update_settings(self, settings: SettingsData) -> None:
        await self.mutate(lambda candidate: setattr(candidate, "settings", settings))

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
