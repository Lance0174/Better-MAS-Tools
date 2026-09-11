"""独立签到、便笺与自动触发的生命周期。"""

import asyncio
from datetime import datetime

from app.core.community_activity import collect_configured_community_activity
from app.core.community_scheduler import community_activity_flow
from app.core.community_sign import community_sign_flow, run_community_sign_in
from app.core.state import state
from app.tools.community_contract import CommunitySignInProgressError
from app.tools.community_sign_provider import has_community_credentials
from app.utils.constants import UTC8
from app.utils.logger import get_logger

logger = get_logger("社区运行")


class CommunityRuntime:
    def __init__(self):
        self.sign_running = False
        self.activity_running = False

    def require_idle(self) -> None:
        if self.sign_running or self.activity_running:
            raise CommunitySignInProgressError(
                "社区请求正在执行，请结束后再修改账号或设置"
            )

    async def sign(self, *, force: bool) -> None:
        async with community_sign_flow():
            self.sign_running = True
            try:
                results = await run_community_sign_in(force=force)
                if results:
                    from app.core.miyoushe_missions import capture

                    capture(results)
                    await state.save_results(results)
            finally:
                self.sign_running = False

    async def activity(self, account_ids: list[str] | None):
        if not state.data.settings.ActivityEnabled:
            return ()
        async with community_activity_flow():
            self.activity_running = True
            try:
                return await collect_configured_community_activity(account_ids)
            finally:
                self.activity_running = False

    async def auto_loop(self) -> None:
        startup = True
        attempted_on = ""
        while True:
            now = datetime.now(tz=UTC8)
            today = now.strftime("%Y-%m-%d")
            settings = state.data.settings
            has_accounts = any(
                has_community_credentials(account)
                and account.get("GameSignAccount", "Enabled")
                for account in state.accounts.values()
            )
            scheduled = (
                settings.ScheduledRun
                and now.strftime("%H:%M") >= settings.ScheduledTime
                and state.data.lastScheduledDate != now.strftime("%Y-%m-%d")
            )
            should_run = (
                settings.Enabled
                and has_accounts
                and attempted_on != today
                and ((startup and settings.RunOnStartup) or scheduled)
            )
            startup = False
            if should_run:
                try:
                    await self.sign(force=False)
                    # 写盘失败也不在本进程内每 30 秒重复访问上游；手动重试不受限。
                    attempted_on = datetime.now(tz=UTC8).strftime("%Y-%m-%d")
                    await state.mutate(
                        lambda data: setattr(
                            data,
                            "lastScheduledDate",
                            datetime.now(tz=UTC8).strftime("%Y-%m-%d"),
                        )
                    )
                except CommunitySignInProgressError:
                    pass
                except Exception as error:
                    attempted_on = datetime.now(tz=UTC8).strftime("%Y-%m-%d")
                    logger.warning(f"自动签到未完成：{type(error).__name__}")
            await asyncio.sleep(30)

runtime = CommunityRuntime()
