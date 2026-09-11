"""隔离本机滑块识别，取消时回收原生库及其进程，避免拖住 Web 后端。"""

import asyncio
import base64
import json
import subprocess
import sys
from pathlib import Path

SLIDE_WORKER_TIMEOUT = 10


async def calculate_slide_distance(background: bytes, target: bytes) -> int:
    root = Path(__file__).resolve().parents[2]
    arguments = [] if getattr(sys, "frozen", False) else [str(root / "main.py")]
    options = (
        {"creationflags": subprocess.CREATE_NO_WINDOW}
        if sys.platform == "win32"
        else {}
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        *arguments,
        "--captcha-slide-worker",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        **options,
    )
    try:
        payload = json.dumps(
            [base64.b64encode(image).decode("ascii") for image in (background, target)]
        ).encode("ascii")
        output, _ = await asyncio.wait_for(
            process.communicate(payload), timeout=SLIDE_WORKER_TIMEOUT
        )
        try:
            result = json.loads(output)
        except (ValueError, UnicodeError):
            raise ValueError("本地滑块识别进程未返回有效结果") from None
        if process.returncode != 0 or not isinstance(result, dict):
            raise ValueError("本地滑块识别进程未完成")
        if result.get("error") == "dependencies":
            raise ValueError("本地滑块依赖不完整，请重新运行源码安装或使用完整桌面包")
        distance = result.get("distance")
        if type(distance) is not int or not 0 <= distance <= 640:
            raise ValueError("本地滑块未能识别此次图片")
        return distance
    except TimeoutError:
        raise ValueError("本地滑块识别超时，已停止识别进程") from None
    finally:
        if process.returncode is None:
            if sys.platform == "win32":
                # venv 的 python.exe 可能再启动实际解释器，必须回收自身的整个子进程树。
                cleanup = await asyncio.create_subprocess_exec(
                    "taskkill",
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                await cleanup.wait()
            else:
                process.kill()
            await process.communicate()
