"""Versus image for the first tweet of the thread, dark theme, 1600 x 900.

results/hero_vs_llms.png  : Jev against the LLM crowd named in TypeSafe's pitch (Claude, GPT, Gemini, DeepSeek)
results/hero_vs_haiku.png : Jev against Claude Haiku 4.5, the only model actually benchmarked

Fonts are downloaded at runtime from Google Fonts into data/fonts (never committed).

Usage: uv run hero_image.py
"""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from bench.common import RESULTS_DIR
from charts import JEV, LLM, SURFACE, TEXT, TEXT_2

FONT_DIR = Path("data/fonts")
UA = "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0"  # old UA so Google serves woff, which PIL reads
FAMILIES = {"bebas": "Bebas+Neue", "montserrat": "Montserrat:700,900", "inter": "Inter:400,700,900"}

W, H = 1600, 900
SS = 2  # supersampling factor


def fetch_fonts() -> dict[str, Path]:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for key, fam in FAMILIES.items():
        req = urllib.request.Request(f"https://fonts.googleapis.com/css?family={fam}", headers={"User-Agent": UA})
        css = urllib.request.urlopen(req).read().decode()
        for i, url in enumerate(re.findall(r"https://fonts\.gstatic\.com[^)]+", css)):
            path = FONT_DIR / f"{key}-{i}.woff"
            if not path.exists():
                path.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA})).read())
            name = ImageFont.truetype(str(path), 20).getname()
            out[f"{key}-{name[1].lower()}"] = path
    return out


def hexrgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def glow(size: tuple[int, int], center: tuple[float, float], color: str, radius: float, strength: float) -> Image.Image:
    w, h = size
    y, x = np.mgrid[0:h, 0:w]
    d = np.sqrt((x - center[0]) ** 2 + (y - center[1]) ** 2) / radius
    a = np.clip(strength * np.exp(-(d**2) * 2.2), 0, 1)
    rgb = np.zeros((h, w, 4), dtype=np.uint8)
    rgb[..., :3] = hexrgb(color)
    rgb[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(rgb, "RGBA")


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def render(fonts: dict[str, Path], right_lines: list[str], right_caption: str, out: Path) -> None:
    w, h = W * SS, H * SS
    img = Image.new("RGBA", (w, h), hexrgb(SURFACE) + (255,))

    # glows, blue left, orange right, blurred
    img.alpha_composite(glow((w, h), (0.22 * w, 0.5 * h), JEV, 0.42 * w, 0.55))
    img.alpha_composite(glow((w, h), (0.80 * w, 0.5 * h), LLM, 0.42 * w, 0.50))
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
    mont_bold = ImageFont.truetype(str(fonts["montserrat-bold"]), int(30 * SS))
    inter_bold = ImageFont.truetype(str(fonts["inter-bold"]), int(26 * SS))
    inter = ImageFont.truetype(str(fonts["inter-regular"]), int(24 * SS))
    d = ImageDraw.Draw(img)
    mid_y = 0.47 * h

    def stack(cx: float, lines: list[str], font: ImageFont.FreeTypeFont, color: str, gap: float) -> float:
        """Draw lines centered on cx, block centered on mid_y. Returns the block's bottom y."""
        boxes = [d.textbbox((0, 0), t, font=font) for t in lines]
        heights = [b[3] - b[1] for b in boxes]
        total = sum(heights) + gap * (len(lines) - 1)
        y = mid_y - total / 2
        for t, b, th in zip(lines, boxes, heights):
            d.text((cx - (b[2] - b[0]) / 2 - b[0], y - b[1]), t, font=font, fill=hexrgb(color))
            y += th + gap
        return y - gap

    def caption(cx: float, y: float, text: str, font: ImageFont.FreeTypeFont, color: str) -> float:
        b = d.textbbox((0, 0), text, font=font)
        d.text((cx - (b[2] - b[0]) / 2 - b[0], y - b[1]), text, font=font, fill=hexrgb(color))
        return y + (b[3] - b[1])

    # left: JEV
    cx_left = 0.26 * w
    bottom = stack(cx_left, ["JEV"], bebas, JEV, 0)
    bottom = caption(cx_left, bottom + 0.045 * h, "TYPESAFE AI", mont_bold, TEXT)
    caption(cx_left, bottom + 0.022 * h, "modèle de décision, sorti il y a 2 jours", inter, TEXT_2)

    # right: the opponent(s)
    cx_right = 0.755 * w
    font = bebas_mid if len(right_lines) <= 2 else bebas_small
    bottom = stack(cx_right, right_lines, font, LLM, 0.012 * h)
    caption(cx_right, bottom + 0.045 * h, right_caption, mont_bold, TEXT)

    # center VS on a dark disc
    cx, cy = 0.5 * w, mid_y
    r = 0.155 * h
    disc = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(disc).ellipse([cx - r, cy - r, cx + r, cy + r], fill=hexrgb(SURFACE) + (235,), outline=hexrgb(TEXT) + (90,), width=int(3 * SS))
    img.alpha_composite(disc)
    d = ImageDraw.Draw(img)
    tw, th = text_size(d, "VS", mont_black)
    box = d.textbbox((0, 0), "VS", font=mont_black)
    d.text((cx - tw / 2 - box[0], cy - th / 2 - box[1]), "VS", font=mont_black, fill=hexrgb(TEXT))

    # top and bottom strips
    top = "2 000 MAILS DE PHISHING  ·  MÊME CONSIGNE  ·  UN APPEL PAR MAIL"
    tw, _ = text_size(d, top, inter_bold)
    d.text((0.5 * w - tw / 2, 0.055 * h), top, font=inter_bold, fill=hexrgb(TEXT_2))
    handle = "@Lbdev__"
    tw, _ = text_size(d, handle, inter_bold)
    d.text((0.5 * w - tw / 2, 0.905 * h), handle, font=inter_bold, fill=hexrgb(TEXT_2))

    img = img.convert("RGB").resize((W, H), Image.LANCZOS)
    img.save(out, optimize=True)
    print("wrote", out)


def main() -> None:
    fonts = fetch_fonts()
    render(fonts, ["CLAUDE", "GPT", "GEMINI", "DEEPSEEK"], "LES LLM CLASSIQUES", RESULTS_DIR / "hero_vs_llms.png")
    render(fonts, ["CLAUDE", "HAIKU 4.5"], "ANTHROPIC", RESULTS_DIR / "hero_vs_haiku.png")


if __name__ == "__main__":
    main()
