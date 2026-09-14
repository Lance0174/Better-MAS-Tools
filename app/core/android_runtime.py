"""手机前台运行入口；复用现有 API 和签到编排，不启动本机监听端口。"""

import asyncio
import json
from datetime import datetime
from urllib.parse import urlsplit

import httpx

from app.core.runtime import runtime
from app.core.state import state
from app.services.android import AndroidStorage, AndroidTransport, NativeCall
from app.services.network import network
from app.tools.community_contract import CommunitySignInProgressError
from app.tools.community_sign_provider import has_community_credentials
from app.utils.constants import UTC8
from app.utils.logger import get_logger

logger = get_logger("手机本地服务")


class AndroidRuntime:
    def __init__(self, call: NativeCall):
        self.call = call
        self.client: httpx.AsyncClient | None = None
        self.startup_task: asyncio.Task | None = None
        self.requests: dict[str, asyncio.Task] = {}
        self.startup_running = False

    async def initialize(self, *, run_startup: bool) -> None:
        from app.main import create_app

        storage = AndroidStorage(self.call)
        state.data = await storage.load()
        state.storage = storage
        network.transport_factory = lambda: AndroidTransport(self.call)
        network.local_connections = False
        network.proxy = None
        if state.data.settings.Proxy:
            raise ValueError("手机本地版不支持桌面代理配置，请清除该配置后重试")
        app = create_app(start_scheduler=False, external_state=True)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        )
        logger.info(f"本地服务启动，账号数={len(state.accounts)}")
        if run_startup:
            self.startup_task = asyncio.create_task(self.sign_on_open())

    async def sign_on_open(self) -> None:
        today = datetime.now(tz=UTC8).strftime("%Y-%m-%d")
        settings = state.data.settings
        if self.startup_running or not (
            settings.Enabled
            and settings.RunOnStartup
            and any(
                has_community_credentials(account)
                and account.get("GameSignAccount", "Enabled")
                for account in state.accounts.values()
            )
            and state.data.lastScheduledDate != today
        ):
            return
        self.startup_running = True
        try:
            # 先持久化尝试日期；闪退或反复打开 App 不自动重复访问上游。
            await state.mutate(
                lambda candidate: setattr(candidate, "lastScheduledDate", today)
            )
            await runtime.sign(force=False)
        except asyncio.CancelledError:
            raise
        except CommunitySignInProgressError:
            logger.info("已有社区任务运行，本次打开应用不重复签到")
        except Exception:
            logger.exception("打开应用时签到未完成，可在签到页查看结果并手动重试")
        finally:
            self.startup_running = False

    async def request(self, serialized: str) -> str:
        payload = json.loads(serialized)
        path = payload["path"]
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc or not parsed.path.startswith("/api/"):
            raise ValueError("本地接口地址不受支持")
        if self.client is None:
            raise RuntimeError("本地服务尚未启动")
        request_id = payload["id"]
        current = asyncio.current_task()
        if current is not None:
            self.requests[request_id] = current
        try:
            response = await self.client.request(
                payload["method"],
                path,
                headers=payload.get("headers") or {},
                content=(payload.get("body") or "").encode("utf-8"),
            )
            return json.dumps(
                {
                    "status": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text,
                }
            )
        except Exception:
            logger.exception("手机本地接口执行失败")
            raise
        finally:
            self.requests.pop(request_id, None)

    def cancel(self, request_id: str) -> None:
        task = self.requests.get(request_id)
        if task is not None:
            task.cancel()
