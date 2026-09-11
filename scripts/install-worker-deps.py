"""用 uv 官方跨平台安装准备 Pyodide 依赖，不改全局工具或代理。"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lock", action="store_true", help="重新解析并生成 pylock.toml"
    )
    parser.add_argument("--proxy", help="仅本次安装使用的 HTTPS 代理")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 13):
        raise SystemExit("请用 Python 3.13 运行；步骤见 docs/DEPLOYMENT.md")
    sibling = Path(sys.executable).parent / ("uv.exe" if os.name == "nt" else "uv")
    executable = str(sibling) if sibling.is_file() else shutil.which("uv")
    if executable is None:
        raise SystemExit("当前环境需要 uv >=0.12.3；无需升级系统 uv")
    version = subprocess.check_output([executable, "--version"], text=True).split()[1]
    if tuple(int(item) for item in version.split(".")[:3]) < (0, 12, 3):
        raise SystemExit("当前环境 uv 太旧；请按 docs/DEPLOYMENT.md 使用隔离工具环境")
    directory = Path(__file__).resolve().parent.parent / "deploy/worker"
    environment = dict(os.environ, UV_HTTP_TIMEOUT="60")
    if args.proxy:
        environment["HTTPS_PROXY"] = args.proxy
    common = [
        "--python",
        sys.executable,
        "--python-platform",
        "wasm32-pyodide2025",
        "--no-build",
    ]
    if args.lock:
        subprocess.run(
            [
                executable,
                "pip",
                "compile",
                "pyproject.toml",
                *common,
                "--extra-index-url",
                "https://index.pyodide.org/0.28.3",
                "--index-strategy",
                "unsafe-best-match",
                "-o",
                "pylock.toml",
            ],
            cwd=directory,
            env=environment,
            check=True,
        )
    subprocess.run(
        [
            executable,
            "pip",
            "install",
            "-r",
            "pylock.toml",
            *common,
            "--preview-features",
            "pylock",
            "--target",
            "python_modules",
        ],
        cwd=directory,
        env=environment,
        check=True,
    )
    # Wrangler 用此标记识别 Pyodide 环境，避免 Windows 临时模块探测失败。
    (directory / "python_modules/pyvenv.cfg").touch(exist_ok=True)
    print("Workers Python 依赖准备完成；未部署。")


if __name__ == "__main__":
    main()
