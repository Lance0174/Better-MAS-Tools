"""从本项目应用离线生成 OpenAPI，不启动服务、不加载用户账号。"""

import json
import sys
from pathlib import Path


def export_openapi() -> None:
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    from app.main import create_app

    destination = root / "frontend/openapi.json"
    destination.write_text(
        json.dumps(
            create_app(start_scheduler=False).openapi(), ensure_ascii=False, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Exported {destination}")


if __name__ == "__main__":
    export_openapi()
