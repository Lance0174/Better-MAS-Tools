"""执行层：本地后端主动出站连接转发层，领取白名单指令并执行后回传。

指令白名单硬编码于 RelayCommandIn；本模块只处理这四类，不做通用代理。
会话与云端模式共用 CloudBaseUrl/CloudPassword；Worker 侧会话是内存态，
遇到 401 自动重新登录换取新 key。
"""

import asyncio
import platform

from app.core.runtime import runtime
from app.core.state import state
from app.models.schema import MasStartIn, MasStopIn
from app.services import mas
from app.services.network import network
from app.services.relay import POLL_HOLD_SECONDS
from app.tools.community_contract import CommunitySignInProgressError
from app.utils.logger import get_logger

logger = get_logger("执行层")

IDLE_POLL_SECONDS = 5
RETRY_SECONDS = 15
REQUEST_TIMEOUT = 40.0


class RelayExecutor:
    def __init__(self):
        self.node_id = (platform.node() or "local-executor")[:80]
        self._session_key = ""

    async def loop(self) -> None:
        while True:
            try:
                settings = state.data.settings
                if not (
                    settings.RelayEnabled
                    and settings.CloudBaseUrl
                    and settings.CloudPassword
                ):
                    await asyncio.sleep(RETRY_SECONDS)
                    continue
                command = await self._poll_once()
                if command is None:
                    await asyncio.sleep(IDLE_POLL_SECONDS)
                else:
                    await self._run(command)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.opt(exception=True).error("执行层循环异常")
                await asyncio.sleep(RETRY_SECONDS)

    def _headers(self) -> dict[str, str]:
        if not self._session_key:
            raise ValueError("执行层尚未登录转发层")
        return {"x-community-session": self._session_key}

    async def _login(self) -> None:
        settings = state.data.settings
        async with network.client(
            trust_env=False, timeout=15, follow_redirects=False
        ) as client:
            response = await client.post(
                settings.CloudBaseUrl.rstrip("/") + "/api/session",
                json={"password": settings.CloudPassword},
            )
            response.raise_for_status()
            session = response.json()
        if not isinstance(session, dict) or not session.get("key"):
            raise ValueError("转发层登录未完成，请检查云端地址与访问密码")
        self._session_key = str(session["key"])
        logger.info("执行层已登录转发层")

    async def _post(self, path: str, payload: dict) -> dict:
        """带会话的 POST；401 时重登一次再试。"""
        settings = state.data.settings
        base = settings.CloudBaseUrl.rstrip("/")
        for attempt in range(2):
            if not self._session_key:
                await self._login()
            async with network.client(
                trust_env=False, timeout=REQUEST_TIMEOUT, follow_redirects=False
            ) as client:
                response = await client.post(
                    base + path, json=payload, headers=self._headers()
                )
            if response.status_code == 401 and attempt == 0:
                self._session_key = ""
                logger.warning("执行层会话失效，正在重新登录")
                continue
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict) or result.get("code", 200) != 200:
                raise ValueError(result.get("message", "转发层响应无效"))
            return result
        raise ValueError("转发层登录后仍未完成请求")

    async def _poll_once(self) -> dict | None:
        result = await self._post(
            "/api/relay/poll", {"nodeId": self.node_id}
        )
        return result.get("data")

    async def _submit(
        self, command_id: str, ok: bool, data: dict, error: str
    ) -> None:
        await self._post(
            "/api/relay/result",
            {
                "nodeId": self.node_id,
                "commandId": command_id,
                "ok": ok,
                "data": data,
                "error": error,
                "finishedAt": "",
            },
        )
        logger.info(f"指令 {command_id} 执行{'成功' if ok else '失败'}")

    async def _run(self, command: dict) -> None:
        command_id = str(command.get("id", ""))
        command_type = str(command.get("type", ""))
        payload = command.get("payload") or {}
        logger.info(f"开始执行指令 {command_type}（{command_id}）")
        try:
            data = await self._execute(command_type, payload)
        except Exception as error:
            logger.opt(exception=error).warning(f"指令 {command_type} 执行失败")
            await self._submit(command_id, False, {}, str(error))
        else:
            await self._submit(command_id, True, data, "")

    async def _execute(self, command_type: str, payload: dict) -> dict:
        if command_type == "mas.snapshot":
            return await mas.snapshot(state.data.settings.MasBaseUrl)
        if command_type == "mas.start":
            body = MasStartIn.model_validate(payload)
            result = await mas.request(
                state.data.settings.MasBaseUrl,
                "/api/dispatch/start",
                payload=body.model_dump(),
            )
            return {"taskId": str(result.get("taskId", ""))}
        if command_type == "mas.stop":
            body = MasStopIn.model_validate(payload)
            await mas.request(
                state.data.settings.MasBaseUrl,
                "/api/dispatch/stop",
                payload=body.model_dump(),
            )
            return {}
        if command_type == "sign.run":
            try:
                await runtime.sign(force=True)
            except CommunitySignInProgressError:
                raise ValueError("本机签到正在进行中，请稍后再试") from None
            return {"message": "签到已在本机执行，结果见运行记录"}
        raise ValueError(f"未知的指令类型：{command_type}")


relay_executor = RelayExecutor()
