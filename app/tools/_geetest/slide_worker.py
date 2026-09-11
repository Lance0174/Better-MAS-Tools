"""滑块识别子进程入口：仅接收两张图片，不接触账号、密钥或网络。"""

import base64
import json
import sys


def main() -> None:
    from .track_detact.slide import _calculate_slide_distance_cv2

    try:
        images = json.loads(sys.stdin.buffer.read(5_400_000))
        if not isinstance(images, list) or len(images) != 2:
            raise ValueError("invalid images")
        background, target = (base64.b64decode(raw, validate=True) for raw in images)
        result = {"distance": _calculate_slide_distance_cv2(background, target)}
    except ImportError:
        result = {"error": "dependencies"}
    except Exception:
        # 不将库异常、输入图像或路径传回 Web API。
        result = {"error": "recognition"}
    print(json.dumps(result), flush=True)
