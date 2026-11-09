"""本机 MAS MCP 的离线契约：协商、工具发现、SSE 和不重复执行。"""

import json

import httpx
import pytest

from app.services import mas
from app.services.network import CommunityNetwork


class FakeMas:
    def __init__(self, *, sse: bool = False, failure: str = "") -> None:
        self.sse = sse
        self.failure = failure
        self.methods: list[str] = []
        self.calls: list[dict] = []
        self.closed = False

    def handle(self, request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://127.0.0.1:36163/mcp"
        assert "text/event-stream" in request.headers["accept"]
        if request.method == "DELETE":
            self.closed = True
            return httpx.Response(204)
        body = json.loads(request.content)
        method = body["method"]
        self.methods.append(method)
        if method == "initialize":
            if self.failure == "unavailable":
                return httpx.Response(404)
            result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}
        else:
            assert request.headers["mcp-session-id"] == "fake-session"
            assert request.headers["mcp-protocol-version"] == "2024-11-05"
            if method == "notifications/initialized":
                assert "id" not in body
                return httpx.Response(202)
            if method == "tools/list":
                result = {
                    "tools": [
                        {"name": name, "inputSchema": {"type": "object"}}
                        for name in mas._TOOLS.values()
                        if self.failure != "missing" or "start" not in name
                    ]
                }
            else:
                assert method == "tools/call"
                params = body["params"]
                self.calls.append(params)
                if self.failure == "timeout":
                    raise httpx.ReadTimeout("not-confirmed", request=request)
                name = params["name"]
                if name == mas._TOOLS["/api/queue/get"]:
                    value = {
                        "code": 200,
                        "index": [{"uid": "queue-1"}],
                        "data": {"queue-1": {"Info": {"Name": "演示队列"}}},
                    }
                elif name == mas._TOOLS["/api/dispatch/runtime-snapshot"]:
                    value = {"tasks": [{"taskId": "run-1", "mode": "AutoProxy"}]}
                else:
                    value = {"code": 200, "taskId": "run-2"}
                if self.failure == "business":
                    value = {"code": 500, "message": "password=must-not-leak"}
                result = {"content": [{"type": "text", "text": json.dumps(value)}]}
                if self.failure == "tool":
                    result["isError"] = True
        message = {"jsonrpc": "2.0", "id": body["id"], "result": result}
        headers = {"Mcp-Session-Id": "fake-session"}
        if self.sse:
            # 心跳与无关通知不能被误当作当前请求的结果。
            content = ': ping\n\ndata: {"jsonrpc":"2.0","method":"notice"}\n\n'
            content += "event: message\ndata: " + json.dumps(message) + "\n\n"
            return httpx.Response(
                200,
                text=content,
                headers={**headers, "Content-Type": "text/event-stream"},
            )
        return httpx.Response(200, json=message, headers=headers)


def install(monkeypatch, fake: FakeMas) -> None:
    monkeypatch.setattr(
        mas,
        "network",
        CommunityNetwork(transport_factory=lambda: httpx.MockTransport(fake.handle)),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("sse", [False, True])
async def test_snapshot_uses_one_mcp_session_and_closes_it(monkeypatch, sse):
    fake = FakeMas(sse=sse)
    install(monkeypatch, fake)
    data = await mas.snapshot("http://127.0.0.1:36163")
    assert data["queues"] == [{"id": "queue-1", "name": "演示队列"}]
    assert data["tasks"][0]["id"] == "run-1"
    assert fake.methods == [
        "initialize",
        "notifications/initialized",
        "tools/list",
        "tools/call",
        "tools/call",
    ]
    assert fake.closed


@pytest.mark.asyncio
async def test_start_passes_flat_arguments_and_only_reports_acceptance(monkeypatch):
    fake = FakeMas()
    install(monkeypatch, fake)
    payload = {"taskId": "queue-1", "mode": "AutoProxy"}
    result = await mas.request(
        "http://127.0.0.1:36163", "/api/dispatch/start", payload=payload
    )
    assert result["taskId"] == "run-2"
    assert fake.calls == [
        {"name": "add_task_api_dispatch_start_post", "arguments": payload}
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "tool", "business", "unavailable"])
async def test_mcp_expected_failures_are_safe(monkeypatch, failure):
    fake = FakeMas(failure=failure)
    install(monkeypatch, fake)
    with pytest.raises(ValueError) as error:
        await mas.request("http://127.0.0.1:36163", "/api/dispatch/start", payload={})
    assert "must-not-leak" not in str(error.value)
    assert "MAS" in str(error.value)
    assert len(fake.calls) <= 1


@pytest.mark.asyncio
async def test_uncertain_start_is_never_retried(monkeypatch):
    fake = FakeMas(failure="timeout")
    install(monkeypatch, fake)
    with pytest.raises(httpx.ReadTimeout):
        await mas.request("http://127.0.0.1:36163", "/api/dispatch/start", payload={})
    assert len(fake.calls) == 1
    assert fake.closed


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://127.0.0.1@external.example",
        "http://localhost/mcp",
        "http://localhost?next=external",
    ],
)
def test_mcp_rejects_non_local_targets(url):
    with pytest.raises(ValueError):
        mas.validate_base_url(url)
