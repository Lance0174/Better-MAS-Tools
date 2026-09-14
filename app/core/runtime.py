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
                logger.info(
                    f"开始{'手动' if force else '自动'}签到，账号数={len(state.accounts)}"
                )
                if state.data.settings.CloudMode:
                    results = await self._sign_via_cloud()
                else:
                    results = await run_community_sign_in(force=force)
                if results:
                    from app.core.miyoushe_missions import capture

                    capture(results)
                    await state.save_results(results)
                completed = sum(
                    item.get("status") in ("成功", "已签到")
                    or bool(item.get("_completed"))
                    for item in results
                )
                logger.info(
                    f"签到执行结束：共{len(results)}项，完成{completed}项，其余{len(results) - completed}项"
                )
            except Exception:
                logger.exception("签到执行异常")
                raise
            finally:
                self.sign_running = False

    async def _sign_via_cloud(self) -> list[dict[str, object]]:
        """云端模式：把本地账号 token 上传云端执行，云端返回结果。

        本地只保存云端返回的签到结果，不把账号 token 写入本机（云端不持久化）。
        未配置云端地址时明确报错，避免静默走回本地执行。
        """
        from app.core.state import state
        from app.services.cloud import sync_sign
        from app.tools.community_sign_provider import (
            COMMUNITY_TOKEN_FIELDS,
            read_community_token,
        )

        settings = state.data.settings
        if not settings.CloudBaseUrl:
            raise ValueError("云端模式需要先在设置中填写云端地址与访问密码")
        accounts = []
        for uid, account in state.accounts.items():
            account_name = account.get("GameSignAccount", "Name") or "默认账号"
            enabled = bool(account.get("GameSignAccount", "Enabled"))
            tokens = {
                field: read_community_token(account, field)
                for field in COMMUNITY_TOKEN_FIELDS
                if read_community_token(account, field)
            }
            if tokens:
                accounts.append(
                    {
                        "uid": str(uid),
                        "name": account_name,
                        "enabled": enabled,
                        "tokens": tokens,
                    }
                )
        if not accounts:
            return []
        logger.info(f"云端模式：上传 {len(accounts)} 个账号到云端执行")
        results = await sync_sign(
            base_url=settings.CloudBaseUrl,
            password=settings.CloudPassword,
            accounts=accounts,
            miyoushe_bbs=settings.MiyousheBbsEnabled,
        )
        return results

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
                    logger.opt(exception=error).error("自动签到未完成")
            await asyncio.sleep(30)


runtime = CommunityRuntime()
