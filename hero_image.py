"""Versus image for the first tweet of the thread, dark theme, 1600 x 900, no sentence anywhere.

results/hero_vs_llms.png  : Jev against the LLM crowd named in TypeSafe's pitch (Claude, GPT, Gemini, DeepSeek)
results/hero_vs_haiku.png : Jev against Claude Haiku 4.5, the only model actually benchmarked

Inputs downloaded or provided at runtime, never committed:
- data/fonts : Bebas Neue, Montserrat, Inter from Google Fonts (fetched here)
- data/brand/typesafe_logo.jpg : the TypeSafe AI logo card (dark mark on pink), the cube mark is cut out of it

Usage: uv run hero_image.py
"""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from bench.common import RESULTS_DIR
from charts import LLM, SURFACE, TEXT

FONT_DIR = Path("data/fonts")
LOGO = Path("data/brand/typesafe_logo.jpg")
UA = "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0"  # old UA so Google serves woff, which PIL reads
FAMILIES = {"bebas": "Bebas+Neue", "montserrat": "Montserrat:900"}

PINK = "#f48aa1"  # sampled from the TypeSafe logo card
W, H = 1600, 900
SS = 2  # supersampling factor


def fetch_fonts() -> dict[str, Path]:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for key, fam in FAMILIES.items():
        req = urllib.request.Request(f"https://fonts.googleapis.com/css?family={fam}", headers={"User-Agent": UA})
        css = urllib.request.urlopen(req).read().decode()
        for url in re.findall(r"https://fonts\.gstatic\.com[^)]+", css):
            path = FONT_DIR / f"{key}-{url.rsplit('/', 1)[1]}"
            if not path.exists():
                path.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA})).read())
            name = ImageFont.truetype(str(path), 20).getname()
            out[f"{key}-{name[1].lower()}"] = path
    return out


def hexrgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def cube_mark(color: str, height: int) -> Image.Image:
    """Cut the cube mark out of the logo card: dark pixels left of the wordmark, recolored, transparent elsewhere."""
    im = np.array(Image.open(LOGO).convert("RGB")).astype(int)
    darkness = np.clip((430 - im.sum(axis=2)) / 200, 0, 1)  # 1 on the mark (sum < 230), 0 on the pink card (sum ~ 540)
    dark = darkness > 0.5
    sub = dark[80:320, 80:260]  # ignore the crop marks in the card's corners
    rows = np.where(sub.any(axis=1))[0]
    y0, y1 = 80 + rows.min(), 80 + rows.max()
    cols = dark[y0 : y1 + 1, 80:260].sum(axis=0)
    xs = np.where(cols > 0)[0]
    x0 = 80 + xs.min()
    x1 = x0 + int(np.argmax(cols[xs.min() :] == 0))  # first empty column after the mark, before the wordmark
    a = darkness[y0 : y1 + 1, x0:x1]
    rgba = np.zeros(a.shape + (4,), dtype=np.uint8)
    rgba[..., :3] = hexrgb(color)
    rgba[..., 3] = (a * 255).astype(np.uint8)
    mark = Image.fromarray(rgba, "RGBA")
    return mark.resize((round(mark.width * height / mark.height), height), Image.LANCZOS)


def glow(size: tuple[int, int], center: tuple[float, float], color: str, radius: float, strength: float) -> Image.Image:
    w, h = size
    y, x = np.mgrid[0:h, 0:w]
    d = np.sqrt((x - center[0]) ** 2 + (y - center[1]) ** 2) / radius
    a = np.clip(strength * np.exp(-(d**2) * 2.2), 0, 1)
    rgb = np.zeros((h, w, 4), dtype=np.uint8)
    rgb[..., :3] = hexrgb(color)
    rgb[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(rgb, "RGBA")


def render(fonts: dict[str, Path], right_lines: list[str], out: Path) -> None:
    w, h = W * SS, H * SS
    img = Image.new("RGBA", (w, h), hexrgb(SURFACE) + (255,))

    # glows, pink left, orange right, blurred
    img.alpha_composite(glow((w, h), (0.22 * w, 0.5 * h), PINK, 0.34 * w, 0.30))
    img.alpha_composite(glow((w, h), (0.80 * w, 0.5 * h), LLM, 0.34 * w, 0.38))
    img = img.filter(ImageFilter.GaussianBlur(6 * SS))

    # diagonal split: a dark band with a thin light edge
    d = ImageDraw.Draw(img)
    top_x, bot_x = 0.545 * w, 0.455 * w
    band = 0.016 * w
    d.polygon([(top_x - band, 0), (top_x + band, 0), (bot_x + band, h), (bot_x - band, h)], fill=hexrgb(SURFACE) + (255,))
    d.line([(top_x, 0), (bot_x, h)], fill=hexrgb(TEXT) + (60,), width=int(2 * SS))

    # subtle diagonal streaks for motion
    streak = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(streak)
    for k in range(-6, 7):
        off = k * 0.09 * w
        sd.line([(top_x + off, 0), (bot_x + off, h)], fill=(255, 255, 255, 10), width=int(1.5 * SS))
    img.alpha_composite(streak)

    bebas = ImageFont.truetype(str(fonts["bebas-regular"]), int(330 * SS))
    bebas_mid = ImageFont.truetype(str(fonts["bebas-regular"]), int(170 * SS))
    bebas_small = ImageFont.truetype(str(fonts["bebas-regular"]), int(104 * SS))
    mont_black = ImageFont.truetype(str(fonts["montserrat-black"]), int(170 * SS))
    d = ImageDraw.Draw(img)
    mid_y = 0.5 * h

    def stack(cx: float, lines: list[str], font: ImageFont.FreeTypeFont, color: str, gap: float, center_y: float) -> tuple[float, float]:
        """Draw lines centered on cx, block centered on center_y. Returns the block's top and bottom y."""
        boxes = [d.textbbox((0, 0), t, font=font) for t in lines]
        heights = [b[3] - b[1] for b in boxes]
        total = sum(heights) + gap * (len(lines) - 1)
        top = y = center_y - total / 2
        for t, b, th in zip(lines, boxes, heights):
            d.text((cx - (b[2] - b[0]) / 2 - b[0], y - b[1]), t, font=font, fill=hexrgb(color))
            y += th + gap
        return top, y - gap

    # left: cube mark above JEV, the pair centered as a block
    cx_left = 0.26 * w
    mark = cube_mark(PINK, int(0.17 * h))
    gap = 0.04 * h
    jev_h = d.textbbox((0, 0), "JEV", font=bebas)[3] - d.textbbox((0, 0), "JEV", font=bebas)[1]
    block_top = mid_y - (mark.height + gap + jev_h) / 2
    img.alpha_composite(mark, (int(cx_left - mark.width / 2), int(block_top)))
    d = ImageDraw.Draw(img)
    stack(cx_left, ["JEV"], bebas, PINK, 0, block_top + mark.height + gap + jev_h / 2)

    # right: the opponent(s)
    cx_right = 0.755 * w
    font = bebas_mid if len(right_lines) <= 2 else bebas_small
    stack(cx_right, right_lines, font, LLM, 0.012 * h, mid_y)

    # center VS on a dark disc
    cx, cy = 0.5 * w, mid_y
    r = 0.155 * h
    disc = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(disc).ellipse([cx - r, cy - r, cx + r, cy + r], fill=hexrgb(SURFACE) + (235,), outline=hexrgb(TEXT) + (90,), width=int(3 * SS))
    img.alpha_composite(disc)
    d = ImageDraw.Draw(img)
    box = d.textbbox((0, 0), "VS", font=mont_black)
    d.text((cx - (box[2] - box[0]) / 2 - box[0], cy - (box[3] - box[1]) / 2 - box[1]), "VS", font=mont_black, fill=hexrgb(TEXT))

    img = img.convert("RGB").resize((W, H), Image.LANCZOS)
    img.save(out, optimize=True)
    print("wrote", out)


def main() -> None:
    fonts = fetch_fonts()
    render(fonts, ["CLAUDE", "GPT", "GEMINI", "DEEPSEEK"], RESULTS_DIR / "hero_vs_llms.png")
    render(fonts, ["CLAUDE", "HAIKU 4.5"], RESULTS_DIR / "hero_vs_haiku.png")


if __name__ == "__main__":
    main()
