"""Reusable drawing helpers for externally authored Pillow motion scenes."""
from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
NAVY = (9, 24, 46)
WHITE = (248, 250, 252)
RED = (239, 68, 68)
GREEN = (34, 197, 94)
YELLOW = (250, 204, 21)
MUTED = (148, 163, 184)


def clamp01(x):
    return max(0.0, min(1.0, x))


def eo_cubic(x):
    return 1 - (1 - clamp01(x)) ** 3


def eo_back(x):
    x = clamp01(x) - 1
    return 1 + 2.70158 * x ** 3 + 1.70158 * x ** 2


def lerp(a, b, x):
    return a + (b - a) * clamp01(x)


def fade(t, at=0, dur=0.6):
    if dur <= 0:
        raise ValueError("Fade duration must be positive.")
    return round(255 * clamp01((t - at) / dur))


@functools.lru_cache(maxsize=256)
def font(px):
    px = max(1, round(px))
    candidates = [ROOT / "fonts" / "Poppins-Bold.ttf", ROOT / "fonts" / "NotoSans.ttf",
                  Path("C:/Windows/Fonts/arialbd.ttf"),
                  Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), px)
    return ImageFont.load_default(size=px)


def canvas(width=1280, height=720, color=NAVY):
    return Image.new("RGB", (width, height), color)


def drawing_layer(image):
    """Draw translucent text/shapes here, then composite onto the RGB base."""
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    return overlay, ImageDraw.Draw(overlay)


def composite(base, overlay):
    if base.size != overlay.size:
        raise ValueError("Base and overlay dimensions must match.")
    return Image.alpha_composite(base.convert("RGBA"), overlay.convert("RGBA")).convert("RGB")


def ctext(draw, xy, text, px, color=WHITE, anchor="mm"):
    draw.text(xy, text, font=font(px), fill=color, anchor=anchor)


def rrect(draw, box, rad=14, fill=NAVY, outline=None, width=1):
    draw.rounded_rectangle(box, radius=rad, fill=fill, outline=outline, width=width)


def slam(draw, t, at, xy, text, px, color=WHITE, dur=0.6):
    if t >= at:
        size = round(px * eo_back((t - at) / dur))
        if size > 0:
            ctext(draw, xy, text, size, tuple(color[:3]) + (fade(t, at, dur),))


def slideup(draw, t, at, xy, text, px, color=WHITE, dur=0.6, dist=80):
    if t >= at:
        p = eo_cubic((t - at) / dur)
        ctext(draw, (xy[0], lerp(xy[1] + dist, xy[1], p)), text, px,
              tuple(color[:3]) + (fade(t, at, dur),))


def _wrap(text, width, px):
    lines = []
    f = font(px)
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            candidate = (line + " " + word).strip()
            if f.getlength(candidate) <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
                line = ""
            for char in word:
                if line and f.getlength(line + char) > width:
                    lines.append(line)
                    line = ""
                line += char
        lines.append(line)
    return lines


def text_box(draw, text, box, px=48, color=WHITE, minimum=18, align="center"):
    """Wrap/shrink text to fit a box; reject overflow instead of clipping it."""
    x0, y0, x1, y1 = box
    width, height = x1 - x0, y1 - y0
    if width <= 0 or height <= 0:
        raise ValueError("Text box must have positive dimensions.")
    for size in range(round(px), round(minimum) - 1, -1):
        lines = _wrap(text, width, size)
        line_h = math.ceil(size * 1.4)
        if len(lines) * line_h <= height and all(font(size).getlength(s) <= width for s in lines):
            y = y0 + (height - len(lines) * line_h) / 2
            for line in lines:
                x = (x0 + x1) / 2 if align == "center" else x0
                draw.text((x, y), line, font=font(size), fill=color,
                          anchor="mt" if align == "center" else "lt")
                y += line_h
            return size
    raise ValueError(f"Text does not fit its box: {text[:80]!r}")


def place_image(target, source, box, fit="cover"):
    """Place an image asset with cover/contain fitting and alpha support."""
    x0, y0, x1, y1 = map(round, box)
    size = (x1 - x0, y1 - y0)
    if min(size) <= 0:
        raise ValueError("Image box must have positive dimensions.")
    with Image.open(source) as loaded:
        asset = loaded.convert("RGBA")
    if fit == "cover":
        asset = ImageOps.fit(asset, size, method=Image.Resampling.LANCZOS)
    elif fit == "contain":
        asset = ImageOps.contain(asset, size, method=Image.Resampling.LANCZOS)
    else:
        raise ValueError("fit must be cover or contain.")
    target.paste(asset, (x0 + (size[0] - asset.width) // 2,
                         y0 + (size[1] - asset.height) // 2), asset)


@dataclass(frozen=True)
class Context:
    width: int
    height: int
    fps: int
    global_time: float
    scene_start: float
    scene_end: float
    scene_id: str
    assets_dir: Path

    def canvas(self, color=NAVY):
        return canvas(self.width, self.height, color)

    def asset(self, relative):
        path = (self.assets_dir / relative).resolve()
        if not path.is_relative_to(self.assets_dir.resolve()) or not path.is_file():
            raise ValueError(f"Missing asset or asset outside input/assets: {relative}")
        return path
