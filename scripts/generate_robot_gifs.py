from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "public" / "robot"
BASE_PATH = ASSET_DIR / "robot-base.png"
SIZE = 512
ART_BOX = 440


def make_art(scale: float = 1.0, offset: tuple[int, int] = (0, 0)) -> Image.Image:
    base = Image.open(BASE_PATH).convert("RGBA")
    alpha = base.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        base = base.crop(bbox)

    target = int(ART_BOX * scale)
    resample = getattr(Image, "Resampling", Image).LANCZOS
    base.thumbnail((target, target), resample)
    frame = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    x = (SIZE - base.width) // 2 + offset[0]
    y = (SIZE - base.height) // 2 + offset[1]
    frame.alpha_composite(base, (x, y))
    return frame


def add_effect(frame: Image.Image, kind: str, progress: float) -> Image.Image:
    if kind == "idle":
        return frame

    if kind == "listening":
        draw = ImageDraw.Draw(frame, "RGBA")
        pulse = 8 + int(6 * (0.5 + 0.5 * math.sin(progress * math.tau)))
        draw.ellipse((SIZE // 2 - pulse, 70 - pulse, SIZE // 2 + pulse, 70 + pulse), outline=(246, 220, 255, 210), width=3)
        return frame

    if kind == "thinking":
        draw = ImageDraw.Draw(frame, "RGBA")
        angle = progress * math.tau
        cx = SIZE // 2 + int(math.cos(angle) * 48)
        cy = 70 + int(math.sin(angle) * 12)
        draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=(242, 224, 255, 230))
        return frame

    if kind == "responding":
        draw = ImageDraw.Draw(frame, "RGBA")
        center_y = 382
        for bar_index, bar_x in enumerate((226, 256, 286)):
            wave = 0.5 + 0.5 * math.sin(progress * math.tau + bar_index * 1.4)
            height = 12 + int(wave * 22)
            draw.rectangle(
                (bar_x - 5, center_y - height // 2, bar_x + 5, center_y + height // 2),
                fill=(224, 216, 255, 210),
            )
        return frame

    if kind == "success":
        draw = ImageDraw.Draw(frame, "RGBA")
        alpha = int(220 * (1 - progress))
        for x, y, phase in ((150, 150, 0.0), (365, 150, 1.8)):
            size = 7 + int(4 * math.sin(progress * math.tau + phase))
            draw.line((x - size, y, x + size, y), fill=(255, 234, 255, alpha), width=3)
            draw.line((x, y - size, x, y + size), fill=(255, 234, 255, alpha), width=3)
        return frame

    if kind == "error":
        draw = ImageDraw.Draw(frame, "RGBA")
        pulse = 9 + int(4 * (0.5 + 0.5 * math.sin(progress * math.tau * 2)))
        draw.ellipse((SIZE // 2 - pulse, 70 - pulse, SIZE // 2 + pulse, 70 + pulse), outline=(255, 150, 185, 230), width=3)
        return frame

    return frame


def to_gif_frame(frame: Image.Image) -> Image.Image:
    alpha = frame.getchannel("A")
    visible = alpha.point(lambda value: 255 if value > 12 else 0)
    rgb = frame.convert("RGB")
    transparent_mask = visible.point(lambda value: 255 - value)
    rgb.paste((0, 255, 0), mask=transparent_mask)
    adaptive = getattr(getattr(Image, "Palette", Image), "ADAPTIVE", Image.ADAPTIVE)
    palette = rgb.convert("P", palette=adaptive, colors=255)
    palette.paste(0, mask=transparent_mask)
    colors = palette.getpalette()
    colors[0:3] = [0, 255, 0]
    palette.putpalette(colors)
    palette.info["transparency"] = 0
    return palette


def write_animation(name: str, kind: str, count: int, duration: int, scale_fn=None) -> None:
    frames = []
    for index in range(count):
        progress = index / count
        scale = scale_fn(progress) if scale_fn else 1.0
        offset = (0, int(math.sin(progress * math.tau) * 3))
        frame = make_art(scale=scale, offset=offset)
        frame = add_effect(frame, kind, progress)
        frames.append(to_gif_frame(frame))

    output = ASSET_DIR / name
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
        transparency=0,
        background=0,
        optimize=False,
    )


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    write_animation("robot-idle.gif", "idle", 16, 80, lambda t: 1.0 + 0.012 * math.sin(t * math.tau))
    write_animation("robot-listening.gif", "listening", 16, 70, lambda t: 1.0 + 0.014 * math.sin(t * math.tau))
    write_animation("robot-thinking.gif", "thinking", 20, 70, lambda t: 1.0 + 0.016 * math.sin(t * math.tau))
    write_animation("robot-responding.gif", "responding", 18, 65, lambda t: 1.0 + 0.018 * math.sin(t * math.tau))
    write_animation("robot-success.gif", "success", 14, 75, lambda t: 0.96 + 0.05 * t)
    write_animation("robot-error.gif", "error", 14, 80, lambda t: 1.0 + 0.012 * math.sin(t * math.tau * 2))
    write_animation("robot-entrance.gif", "success", 18, 55, lambda t: 0.82 + 0.18 * t)


if __name__ == "__main__":
    main()
