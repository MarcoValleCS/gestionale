"""Genera le icone della webapp (PNG) usate da Android, iPhone e browser.

Uso:  python scripts/generate_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "static" / "icons"
TOP = (37, 99, 235)
BOTTOM = (124, 58, 237)


def gradient(size):
    strip = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / max(size - 1, 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM))
        strip.putpixel((0, y), color)
    return strip.resize((size, size))


def draw_box(draw, size, margin_ratio=0.24):
    side = size * (1 - 2 * margin_ratio)
    depth = side * 0.32
    top = size * margin_ratio
    left = (size - side) / 2
    right = left + side
    bottom = top + side
    line_width = max(2, int(size * 0.035))
    white = (255, 255, 255)
    # faccia frontale
    draw.rectangle([left, top + depth, right, bottom], outline=white, width=line_width)
    # prospettiva (alto e lato destro)
    draw.line([left, top + depth, left + depth, top, right + depth, top], fill=white, width=line_width)
    draw.line([right + depth, top, right + depth, bottom - depth, right, bottom], fill=white, width=line_width)
    draw.line([left + depth, top, left + depth, bottom - depth], fill=white, width=line_width)
    draw.line([left + depth, bottom - depth, right + depth, bottom - depth], fill=white, width=line_width)


def make_icon(size, path, maskable=False):
    image = gradient(size).convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw_box(draw, size, margin_ratio=0.34 if maskable else 0.24)
    image.save(path, "PNG")
    print(f"creata {path}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    make_icon(192, OUT / "icon-192.png")
    make_icon(512, OUT / "icon-512.png")
    make_icon(512, OUT / "icon-maskable-512.png", maskable=True)
    make_icon(180, OUT / "apple-touch-icon.png")
    make_icon(32, OUT / "favicon-32.png")

    favicon = gradient(64).convert("RGBA")
    draw_box(ImageDraw.Draw(favicon), 64)
    favicon.save(BASE / "static" / "favicon.ico", sizes=[(16, 16), (32, 32), (64, 64)])
    print(f"creata {BASE / 'static' / 'favicon.ico'}")


if __name__ == "__main__":
    main()
