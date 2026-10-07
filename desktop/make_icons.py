"""Gera os icones do aplicativo a partir da marca do Monitora Pet.

A marca e a mesma do componente front/src/components/BrandMark.tsx: uma pata de
gato enquadrada pelos cantos de foco de uma camera, sobre um bloco arredondado
com o verde da identidade. Abaixo de 48px os cantos de foco sao omitidos e a
pata ocupa mais area, para o icone continuar legivel na barra de tarefas.

Uso: python desktop/make_icons.py
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "front" / "src-tauri" / "icons"

SUPERSAMPLE = 8
TILE = 32.0
TILE_RADIUS = 9.5
GRADIENT_START = (125, 156, 99)
GRADIENT_END = (71, 96, 59)
BRACKET_ALPHA = 140
BRACKET_WIDTH = 1.5
BRACKETS_MIN_SIZE = 48

# Pata em coordenadas locais de 24 unidades, igual ao BrandMark.
TOES = [(4.3, 10.6, 1.9, 2.5), (9.3, 7.3, 2.1, 2.9), (14.7, 7.3, 2.1, 2.9), (19.7, 10.6, 1.9, 2.5)]
PAD = [
    ((12.0, 12.4), (8.9, 12.4), (6.4, 14.5), (6.4, 17.0)),
    ((6.4, 17.0), (6.4, 19.1), (8.2, 20.4), (10.1, 19.9)),
    ((10.1, 19.9), (11.3, 19.57), (12.7, 19.57), (13.9, 19.9)),
    ((13.9, 19.9), (15.8, 20.4), (17.6, 19.1), (17.6, 17.0)),
    ((17.6, 17.0), (17.6, 14.5), (15.1, 12.4), (12.0, 12.4)),
]
PAW_BOX = (2.4, 4.4, 21.6, 20.2)
BRACKETS = [
    [(10.5, 6.5), (6.5, 6.5), (6.5, 10.5)],
    [(21.5, 6.5), (25.5, 6.5), (25.5, 10.5)],
    [(10.5, 25.5), (6.5, 25.5), (6.5, 21.5)],
    [(21.5, 25.5), (25.5, 25.5), (25.5, 21.5)],
]


def bezier(p0, p1, p2, p3, steps=48):
    points = []
    for index in range(steps + 1):
        t = index / steps
        u = 1 - t
        x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points


def paw_transform(target_width: float):
    """Centraliza a pata no bloco de 32 unidades com a largura pedida."""
    left, top, right, bottom = PAW_BOX
    scale = target_width / (right - left)
    offset_x = (TILE - target_width) / 2 - left * scale
    offset_y = (TILE - (bottom - top) * scale) / 2 - top * scale
    return scale, offset_x, offset_y


def gradient_tile(pixels: int) -> Image.Image:
    tile = Image.new("RGB", (pixels, pixels))
    draw = ImageDraw.Draw(tile)
    span = 2 * (pixels - 1)
    for diagonal in range(span + 1):
        ratio = diagonal / span
        color = tuple(round(a + (b - a) * ratio) for a, b in zip(GRADIENT_START, GRADIENT_END))
        draw.line([(diagonal, 0), (0, diagonal)], fill=color)
    mask = Image.new("L", (pixels, pixels), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, pixels - 1, pixels - 1], radius=TILE_RADIUS * pixels / TILE, fill=255
    )
    tile = tile.convert("RGBA")
    tile.putalpha(mask)
    return tile


def render(size: int) -> Image.Image:
    pixels = size * SUPERSAMPLE
    unit = pixels / TILE
    image = gradient_tile(pixels)
    draw_brackets = size >= BRACKETS_MIN_SIZE

    if draw_brackets:
        overlay = Image.new("RGBA", (pixels, pixels), (255, 255, 255, 0))
        pen = ImageDraw.Draw(overlay)
        width = max(1, round(BRACKET_WIDTH * unit))
        for arm in BRACKETS:
            points = [(x * unit, y * unit) for x, y in arm]
            pen.line(points, fill=(255, 255, 255, BRACKET_ALPHA), width=width, joint="curve")
            for x, y in (points[0], points[-1]):
                pen.ellipse([x - width / 2, y - width / 2, x + width / 2, y + width / 2],
                            fill=(255, 255, 255, BRACKET_ALPHA))
        image = Image.alpha_composite(image, overlay)

    scale, offset_x, offset_y = paw_transform(15.0 if draw_brackets else 19.0)

    def place(x: float, y: float) -> tuple[float, float]:
        return ((x * scale + offset_x) * unit, (y * scale + offset_y) * unit)

    paw = ImageDraw.Draw(image)
    for cx, cy, rx, ry in TOES:
        left, top = place(cx - rx, cy - ry)
        right, bottom = place(cx + rx, cy + ry)
        paw.ellipse([left, top, right, bottom], fill=(255, 255, 255, 255))
    outline = []
    for segment in PAD:
        outline.extend(place(*point) for point in bezier(*segment))
    paw.polygon(outline, fill=(255, 255, 255, 255))

    return image.resize((size, size), Image.LANCZOS)


def circular(image: Image.Image) -> Image.Image:
    size = image.width
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size * 4 - 1, size * 4 - 1], fill=255)
    rounded = image.copy()
    rounded.putalpha(mask.resize((size, size), Image.LANCZOS))
    return rounded


def inset(image: Image.Image, ratio: float) -> Image.Image:
    size = image.width
    inner = max(1, round(size * ratio))
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(image.resize((inner, inner), Image.LANCZOS), ((size - inner) // 2,) * 2)
    return canvas


def write_ico(path: Path, sizes: list[int]) -> None:
    """Monta o .ico com um desenho proprio por tamanho.

    O Pillow so sabe reduzir uma imagem mestra para todas as entradas, o que
    borraria justamente os tamanhos pequenos, que usam a variante sem os cantos
    de foco. Entradas ate 64px saem como DIB de 32 bits (o formato que qualquer
    Windows le) e a de 256px sai como PNG, como manda o padrao.
    """
    entries = []
    for size in sizes:
        image = render(size)
        if size >= 256:
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            entries.append((size, buffer.getvalue()))
            continue

        rows = image.load()
        pixel_data = bytearray()
        for y in range(size - 1, -1, -1):
            for x in range(size):
                r, g, b, a = rows[x, y]
                pixel_data += bytes((b, g, r, a))
        mask_stride = ((size + 31) // 32) * 4
        mask_data = bytes(mask_stride * size)
        header = struct.pack(
            "<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, len(pixel_data) + len(mask_data), 0, 0, 0, 0
        )
        entries.append((size, header + bytes(pixel_data) + mask_data))

    offset = 6 + 16 * len(entries)
    directory = b""
    payload = b""
    for size, data in entries:
        dimension = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset)
        payload += data
        offset += len(data)
    path.write_bytes(struct.pack("<HHH", 0, 1, len(entries)) + directory + payload)


def main() -> None:
    written = 0
    for path in sorted(ICON_DIR.rglob("*.png")):
        size = Image.open(path).size[0]
        image = render(size)
        if path.name.endswith("_round.png"):
            image = circular(image)
        elif path.name.endswith("_foreground.png"):
            image = inset(image, 0.66)
        image.save(path)
        written += 1

    for ico in (ICON_DIR / "icon.ico", ROOT / "desktop" / "monitorapet.ico"):
        write_ico(ico, [16, 24, 32, 48, 64, 128, 256])
        written += 1

    render(1024).save(ICON_DIR / "icon.icns", format="ICNS")
    written += 1

    print(f"{written} arquivos de icone gerados")


if __name__ == "__main__":
    main()
