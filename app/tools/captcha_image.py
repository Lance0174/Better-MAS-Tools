"""验证码仅解码有尺寸上限的单帧 PNG/JPEG，不启用文档、字体或其它图像插件。"""

import io
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image


@contextmanager
def open_captcha_image(raw: bytes) -> Iterator["Image.Image"]:
    from PIL import Image

    if not raw or len(raw) > 2_000_000:
        raise ValueError("验证码图片大小无效")
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        # 验证码不使用 EXIF / 文本 / 动画信息；在交给旧版 WASM 解码器前去除可选元数据。
        clean = bytearray(raw[:8])
        offset = 8
        while offset < len(raw):
            length = int.from_bytes(raw[offset : offset + 4], "big")
            end = offset + length + 12
            if end > len(raw) or end <= offset + 11:
                raise ValueError("验证码 PNG 格式无效")
            kind = raw[offset + 4 : offset + 8]
            if kind in {b"acTL", b"fcTL", b"fdAT"}:
                raise ValueError("验证码不支持动画图片")
            if kind in {b"IHDR", b"PLTE", b"tRNS", b"IDAT", b"IEND"}:
                clean.extend(raw[offset:end])
            offset = end
        raw = bytes(clean)
    with Image.open(io.BytesIO(raw), formats=("PNG", "JPEG")) as image:
        if not (1 <= image.width <= 2048 and 1 <= image.height <= 2048):
            raise ValueError("验证码图片尺寸无效")
        yield image
