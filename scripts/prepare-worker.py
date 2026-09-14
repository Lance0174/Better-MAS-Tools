"""复制本仓运行源码与构建前端到 Workers 目录；不会部署或读取账号。"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
target = ROOT / "deploy/worker"
if not (ROOT / "frontend/dist/index.html").is_file():
    raise SystemExit("请先在 frontend 执行 yarn build")
shutil.copytree(
    ROOT / "app",
    target / "src/app",
    dirs_exist_ok=True,
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
)
shutil.copytree(ROOT / "frontend/dist", target / "web", dirs_exist_ok=True)
shutil.copytree(ROOT / "docs/licenses", target / "web/licenses", dirs_exist_ok=True)
for name in ("LICENSE", "NOTICE.md"):
    shutil.copy2(ROOT / name, target / "web" / name)
(target / "web/_headers").write_text(
    "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n"
    "  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://doc.auto-mas.top; font-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'\n"
    "/captcha.html\n  Cache-Control: no-store\n  ! Content-Security-Policy\n"
    "  Content-Security-Policy: default-src 'none'; script-src 'self' 'unsafe-eval' 'unsafe-inline' https://*.geetest.com https://*.geevisit.com https://*.gsensebot.com http://*.geetest.com http://*.geevisit.com http://*.gsensebot.com; style-src 'self' 'unsafe-inline' https://*.geetest.com https://*.geevisit.com https://*.gsensebot.com; img-src data: blob: https://*.geetest.com https://*.geevisit.com https://*.gsensebot.com http://*.geetest.com http://*.geevisit.com http://*.gsensebot.com; connect-src https://*.geetest.com https://*.geevisit.com https://*.gsensebot.com http://*.geetest.com http://*.geevisit.com http://*.gsensebot.com; frame-src https://*.geetest.com; base-uri 'none'; form-action 'none'; frame-ancestors 'self'\n"
    "/captcha.js\n  Cache-Control: no-store\n"
    "/captcha.css\n  Cache-Control: no-store\n",
    encoding="utf-8",
)
print("Workers 源码与静态前端已准备；未部署。")
