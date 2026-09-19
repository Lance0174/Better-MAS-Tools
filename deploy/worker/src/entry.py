"""纯 Cloudflare 入口：静态前端、单用户 Durable Object、Cron 唤醒。"""

import asyncio
from datetime import datetime
from urllib.parse import urlsplit

from workers import DurableObject, Response, WorkerEntrypoint, asgi


class Community(DurableObject):
    def __init__(self, ctx, env):
        super().__init__(ctx, env)
        self.ready = False
        self.initializing = asyncio.Lock()

    async def initialize(self):
        async with self.initializing:
            if self.ready:
                return
            from app.core.state import state
            from app.main import create_app
            from app.services.access import RemoteAccess
            from app.services.cloudflare import DurableStorage, FetchTransport
            from app.services.network import network

            try:
                origin = self.env.COMMUNITY_PUBLIC_ORIGIN
                password = self.env.COMMUNITY_ACCESS_PASSWORD
                encryption_key = self.env.COMMUNITY_ENCRYPTION_KEY
            except AttributeError as error:
                raise ValueError(
                    "Workers 缺少必需环境变量，请在项目根目录 .env 或 Wrangler secrets 中配置"
                ) from error
            if not all(
                isinstance(value, str) and value.strip()
                for value in (origin, password, encryption_key)
            ):
                raise ValueError(
                    "Workers 缺少必需环境变量，请在项目根目录 .env 或 Wrangler secrets 中配置"
                )
            access = RemoteAccess(origin.rstrip("/"), password)
            store = DurableStorage(self.ctx.storage, encryption_key)
            state.data = store.load()
            state.storage = store
            network.transport_factory = FetchTransport
            network.local_connections = False
            network.proxy = None
            if state.data.settings.Proxy:
                raise ValueError("云端配置含本机代理，请从空配置启动 Workers")
            self.app = create_app(
                start_scheduler=False, remote=access, external_state=True
            )
            from app.services.relay import DurableRelayStore

            self.relay_store = DurableRelayStore(self.ctx.storage, encryption_key)
            self.app.state.relay_store = self.relay_store
            self.ready = True

    async def fetch(self, request):
        await self.initialize()
        return await asgi.fetch(self.app, request, self.env, self.ctx)

    async def tick(self):
        await self.initialize()
        from app.core.runtime import runtime
        from app.core.state import state
        from app.tools.community_contract import CommunitySignInProgressError
        from app.utils.constants import UTC8

        now = datetime.now(tz=UTC8)
        settings = state.data.settings
        today = now.strftime("%Y-%m-%d")
        if not (
            settings.Enabled
            and settings.ScheduledRun
            and now.strftime("%H:%M") >= settings.ScheduledTime
            and state.data.lastScheduledDate != today
        ):
            return
        if runtime.sign_running or runtime.activity_running:
            return
        # 先保存当日尝试标记，防止运行器重启或重试再次自动访问上游；失败可手动重试。
        await state.mutate(lambda data: setattr(data, "lastScheduledDate", today))
        try:
            await runtime.sign(force=False)
        except CommunitySignInProgressError:
            pass
        finally:
            # 顺带清理转发层过期指令，保持 Durable Object 存储干净。
            self.relay_store.sweep()


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        path = urlsplit(request.url).path
        if path == "/healthz" or path.startswith("/api/"):
            try:
                return await self.env.COMMUNITY.getByName("community").fetch(request)
            except Exception:
                return Response.json(
                    {
                        "code": 503,
                        "status": "error",
                        "message": "云端服务暂不可用，请检查部署配置和数据密钥",
                    },
                    status=503,
                    headers={"Cache-Control": "no-store"},
                )
        return await self.env.ASSETS.fetch(request)

    async def scheduled(self, controller, env, ctx):
        await self.env.COMMUNITY.getByName("community").tick()
