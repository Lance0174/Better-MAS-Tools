"""生成独立版的几何社区图标，不使用 MAS 团队商标或游戏美术。"""

from pathlib import Path

from PIL import Image, ImageDraw

destination = Path(__file__).resolve().parent.parent / "frontend/assets/community.ico"
canvas = Image.new("RGBA", (256, 256))
draw = ImageDraw.Draw(canvas)
draw.rounded_rectangle((8, 8, 248, 248), radius=56, fill="#1677ff")
for x, y in ((49, 49), (137, 49), (49, 137), (137, 137)):
    draw.rounded_rectangle((x, y, x + 70, y + 70), radius=22, fill="#ffffff")
destination.parent.mkdir(parents=True, exist_ok=True)
canvas.save(destination, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(destination)
