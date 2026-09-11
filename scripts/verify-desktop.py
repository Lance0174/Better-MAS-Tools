"""检查 Windows 发行包及隔离识别进程；只使用随机图片和全新的空账号目录。"""

import argparse
import base64
import io
import json
import os
import random
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from PIL import Image


def verify(directory: Path) -> None:
    backend = directory / "resources/backend/community-backend.exe"
    application = directory / "BetterMASTools.exe"
    for path in (
        backend,
        application,
        directory / "resources/LICENSE",
        directory / "resources/NOTICE.md",
    ):
        if not path.is_file():
            raise ValueError(f"发行包缺少文件：{path.name}")

    background = Image.frombytes("RGB", (150, 100), random.Random(37).randbytes(45_000))
    images = []
    for image in (background, background.crop((37, 20, 67, 60))):
        output = io.BytesIO()
        image.save(output, "PNG")
        images.append(base64.b64encode(output.getvalue()).decode("ascii"))
    result = subprocess.run(
        [str(backend), "--captcha-slide-worker"],
        input=json.dumps(images).encode("ascii"),
        capture_output=True,
        timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=True,
    )
    if json.loads(result.stdout).get("distance") != 37:
        raise ValueError("发行包内滑块识别进程校验失败")

    with tempfile.TemporaryDirectory(
        prefix="bmasc-release-", ignore_cleanup_errors=True
    ) as raw:
        temporary = Path(raw)
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("COMMUNITY_")
        }
        environment.pop("ELECTRON_RUN_AS_NODE", None)
        environment["COMMUNITY_DATA_DIR"] = raw
        desktop = subprocess.Popen(
            [str(application), "--smoke-test"],
            env=environment,
            cwd=directory,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            session_file = temporary / "desktop-session.json"
            deadline = time.monotonic() + 30
            while not session_file.exists():
                if desktop.poll() is not None or time.monotonic() > deadline:
                    raise ValueError("发行包启动失败或超时")
                time.sleep(0.05)
            session = json.loads(session_file.read_text(encoding="utf-8"))
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(session["origin"] + "/healthz", timeout=5) as response:
                if json.load(response).get("application") != "better-mas-community":
                    raise ValueError("发行包健康检查失败")
            with opener.open(
                session["origin"] + "/captcha.html", timeout=5
            ) as response:
                if response.status != 200:
                    raise ValueError("发行包验证码页面不可访问")
            if desktop.wait(timeout=25) != 0 or session_file.exists():
                raise ValueError("发行包没有正常退出并清理会话")
        finally:
            if desktop.poll() is None:
                subprocess.run(
                    ["taskkill", "/PID", str(desktop.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False,
                )
                desktop.wait(timeout=10)
    print(
        "PASS: packaged slide worker, empty-data startup, captcha page, clean shutdown"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    verify(parser.parse_args().directory.resolve())
