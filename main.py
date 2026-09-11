"""独立后端入口；桌面模式通过管道向 Electron 报告就绪并跟随父进程退出。"""

import argparse
import asyncio
import os
import socket
import sys
import threading

import uvicorn

from app.utils.logger import intercept_standard_logging


async def serve_desktop(server: uvicorn.Server, listener: socket.socket) -> None:
    def watch_parent() -> None:
        # Electron 持有 stdin 的写端；正常关闭或崩溃都会产生 EOF。
        sys.stdin.buffer.read()
        server.should_exit = True

    threading.Thread(target=watch_parent, daemon=True, name="desktop-parent").start()
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    while not server.started and not serving.done():
        await asyncio.sleep(0.05)
    if server.started:
        print(f"COMMUNITY_READY {listener.getsockname()[1]}", flush=True)
    await serving


def main() -> None:
    intercept_standard_logging()
    parser = argparse.ArgumentParser(description="更好的MAS工具包")
    parser.add_argument("--port", type=int, default=37164)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--remote",
        action="store_true",
        help="启用远端访问认证，需配置公开来源与访问密码",
    )
    parser.add_argument("--desktop", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.remote:
        os.environ["COMMUNITY_REMOTE"] = "1"
    if (
        args.host not in {"127.0.0.1", "localhost", "::1"}
        and os.environ.get("COMMUNITY_REMOTE") != "1"
    ):
        parser.error("非环回监听必须启用 --remote 并配置访问认证")
    if args.desktop and (args.remote or os.environ.get("COMMUNITY_REMOTE") == "1"):
        parser.error("桌面模式不能同时启用远端监听")
    config = uvicorn.Config(
        "app.main:app",
        host=args.host,
        port=args.port,
        access_log=False,
        loop="asyncio",
        http="h11",
        ws="none",
        lifespan="on",
        log_config=None,
        timeout_graceful_shutdown=8,
    )
    if not args.desktop:
        uvicorn.Server(config).run()
        return
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        # 端口由本后端直接占用，避免先查空闲端口再启动产生竞争。
        listener.bind(("127.0.0.1", args.port))
        listener.listen(128)
        asyncio.run(serve_desktop(uvicorn.Server(config), listener))


if __name__ == "__main__":
    if sys.argv[1:] == ["--captcha-slide-worker"]:
        from app.tools._geetest.slide_worker import main as recognize_slide

        recognize_slide()
    else:
        main()
