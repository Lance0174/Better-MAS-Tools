"""本地合成图片验证解码格式、尺寸和元数据边界。"""

import io
import struct
import zlib

import pytest
from PIL import Image

from app.tools.captcha_image import open_captcha_image


def picture(format="PNG", size=(24, 16)):
    output = io.BytesIO()
    Image.new("RGB", size, (20, 60, 90)).save(output, format=format)
    return output.getvalue()


@pytest.mark.parametrize("format", ["PNG", "JPEG"])
def test_accepts_static_captcha_images(format):
    with open_captcha_image(picture(format)) as image:
        assert image.convert("L").size == (24, 16)


@pytest.mark.parametrize("format", ["TIFF", "GIF", "BMP"])
def test_rejects_unneeded_decoders(format):
    with pytest.raises(OSError, match="cannot identify"):
        with open_captcha_image(picture(format)):
            pytest.fail("unsupported image opened")


def test_strips_png_metadata_before_decoder_and_rejects_animation():
    raw = picture()
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
    poisoned = raw[:33] + chunk(b"eXIf", b"invalid exif" * 1000) + raw[33:]
    with open_captcha_image(poisoned) as image:
        assert "exif" not in image.info
        assert image.convert("RGB").getpixel((0, 0)) == (20, 60, 90)
    with pytest.raises(ValueError, match="动画"):
        with open_captcha_image(raw[:33] + chunk(b"acTL", struct.pack("!II", 2, 0)) + raw[33:]):
            pytest.fail("animated image opened")


def test_rejects_oversized_dimensions_before_loading_pixels():
    with pytest.raises(ValueError, match="尺寸"):
        with open_captcha_image(picture(size=(2049, 1))):
            pytest.fail("oversized image opened")
