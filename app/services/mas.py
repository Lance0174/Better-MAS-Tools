"""通过本机 MAS 的 Streamable HTTP MCP 查询队列、启动和停止任务。"""

import asyncio
import json
from urllib.parse import urlsplit

import httpx

from app.services.network import network

_TOOLS = {
    "/api/queue/get": "get_queues_api_queue_get_post",
    "/api/dispatch/runtime-snapshot": (
        "get_task_runtime_snapshot_api_dispatch_runtime_snapshot_get"
    ),
    "/api/dispatch/start": "add_task_api_dispatch_start_post",
    "/api/dispatch/stop": "stop_task_api_dispatch_stop_post",
}
_PROTOCOL_VERSION = "2024-11-05"
_MAX_RESPONSE_BYTES = 8_000_000


def validate_base_url(value: str) -> str:
    url = urlsplit(value)
    if (
        url.scheme not in {"http", "https"}
        or url.hostname not in {"127.0.0.1", "localhost", "::1"}
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in {"", "/"}
    ):
        raise ValueError("MAS 地址必须是服务所在电脑的 localhost 或环回 IP 地址")
    if url.port is not None and not 1 <= url.port <= 65535:
        raise ValueError("MAS 端口无效")
    return value.rstrip("/")


class MasMcpClient:
    """仅调用四个已知工具；不暴露任意工具执行，也不重试任务变更。"""

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self.client = client
        self.url = validate_base_url(base_url) + "/mcp"
        self.headers = {"Accept": "application/json, text/event-stream"}
        self.sequence = 0
        self.tools: set[str] = set()

    async def _rpc(self, method: str, params: dict, *, notify: bool = False) -> dict:
        self.sequence += 1
        body = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notify:
            body["id"] = self.sequence
        async with self.client.stream(
            "POST", self.url, json=body, headers=self.headers
        ) as response:
            if response.status_code == 404:
                raise ValueError(
                    "MAS MCP 尚未就绪，请确认 MAS 已启动且未关闭 AUTO_MAS_ENABLE_MCP，稍后重试"
                )
            response.raise_for_status()
            if session_id := response.headers.get("mcp-session-id"):
                self.headers["Mcp-Session-Id"] = session_id
            if notify:
                return {}
            if "text/event-stream" in response.headers.get("content-type", ""):
                result = await self._read_event(response, self.sequence)
            else:
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > _MAX_RESPONSE_BYTES:
                        raise ValueError("MAS MCP 响应过大，请在 MAS 中检查队列配置")
                try:
                    result = json.loads(raw)
                except ValueError:
                    raise ValueError(
                        "MAS MCP 返回格式无效，请更新 MAS 后重试"
                    ) from None
        if (
            not isinstance(result, dict)
            or result.get("id") != self.sequence
            or "error" in result
            or not isinstance(result.get("result"), dict)
        ):
            raise ValueError("MAS MCP 未完成请求，请在 MAS 中检查状态")
        return result["result"]

    @staticmethod
    async def _read_event(response: httpx.Response, request_id: int) -> dict:
        # Streamable HTTP 的一次 POST 可返回 SSE；收到对应响应即关流，避免等待永久流结束。
        parts: list[str] = []
        size = 0
        async for line in response.aiter_lines():
            size += len(line.encode("utf-8"))
            if size > _MAX_RESPONSE_BYTES:
                raise ValueError("MAS MCP 响应过大，请在 MAS 中检查队列配置")
            if line.startswith("data:"):
                parts.append(line[5:].lstrip(" "))
            elif not line and parts:
                event = json.loads("\n".join(parts))
                parts.clear()
                if isinstance(event, dict) and event.get("id") == request_id:
                    return event
        raise ValueError("MAS MCP 响应中断，请刷新运行状态")

    async def initialize(self) -> None:
        result = await self._rpc(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "Better-MAS-Tools", "version": "1"},
            },
        )
        version = result.get("protocolVersion")
        if version not in {_PROTOCOL_VERSION, "2025-03-26", "2025-06-18"}:
            raise ValueError("MAS MCP 协议版本不兼容，请更新 MAS 或本工具")
        self.headers["MCP-Protocol-Version"] = version
        await self._rpc("notifications/initialized", {}, notify=True)
        cursor = None
        seen: set[str] = set()
        for _ in range(20):
            page = await self._rpc("tools/list", {"cursor": cursor} if cursor else {})
            for tool in page.get("tools", []):
                if isinstance(tool, dict) and isinstance(tool.get("name"), str):
                    self.tools.add(tool["name"])
            cursor = page.get("nextCursor")
            if not cursor:
                return
            if not isinstance(cursor, str) or cursor in seen:
                break
            seen.add(cursor)
        raise ValueError("MAS MCP 工具列表不完整，请更新 MAS 后重试")

    async def call(self, path: str, payload: dict | None = None) -> dict:
        name = _TOOLS.get(path)
        if name is None or name not in self.tools:
            raise ValueError("MAS MCP 缺少所需的队列或任务工具，请更新 MAS 并启用 MCP")
        result = await self._rpc(
            "tools/call", {"name": name, "arguments": payload or {}}
        )
        if result.get("isError"):
            raise ValueError("MAS 未完成该操作，请在 MAS 中查看任务状态")
        data = result.get("structuredContent")
        if not isinstance(data, dict):
            content = result.get("content", [])
            text = next(
                (
                    item.get("text")
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                ),
                "",
            )
            try:
                data = json.loads(text)
            except (ValueError, TypeError):
                raise ValueError("MAS MCP 未返回有效的操作结果，请刷新状态") from None
        # 上游错误文本可能携带内部数据，不转发原文；200 仅表示受理，不代表任务完成。
        if (
            not isinstance(data, dict)
            or data.get("code", 200) != 200
            or data.get("status") == "error"
        ):
            raise ValueError("MAS 未完成该操作，请在 MAS 中查看任务状态")
        return data

    async def close(self) -> None:
        if "Mcp-Session-Id" not in self.headers:
            return
        try:
            await self.client.delete(self.url, headers=self.headers, timeout=2)
        except httpx.HTTPError:
            # 服务可能不支持会话终止；不能因此将已受理的任务显示为失败。
            pass


async def _execute(base_url: str, calls: list[tuple[str, dict | None]]) -> list[dict]:
    if not network.local_connections:
        raise ValueError("当前运行环境无法连接本机 MAS，请使用桌面版或 Linux 后端")
    base = validate_base_url(base_url)
    async with network.client(
        trust_env=False, timeout=15, follow_redirects=False
    ) as client:
        session = MasMcpClient(client, base)
        try:
            async with asyncio.timeout(45):
                await session.initialize()
                return [await session.call(path, payload) for path, payload in calls]
        finally:
            await session.close()


async def request(base_url: str, path: str, *, payload: dict | None = None) -> dict:
    return (await _execute(base_url, [(path, payload)]))[0]


async def snapshot(base_url: str) -> dict:
    queues, running = await _execute(
        base_url,
        [("/api/queue/get", {}), ("/api/dispatch/runtime-snapshot", None)],
    )
    queue_data = queues.get("data", {})
    return {
        "baseUrl": validate_base_url(base_url),
        "queues": [
            {
                "id": str(item["uid"]),
                "name": str(
                    (queue_data.get(item["uid"], {}).get("Info") or {}).get("Name")
                    or item["uid"]
                ),
            }
            for item in queues.get("index", [])
        ],
        "tasks": [
            {
                "id": str(item["taskId"]),
                "mode": str(item.get("mode", "")),
                "stopping": bool(item.get("stopping")),
            }
            for item in running.get("tasks", [])
        ],
    }
