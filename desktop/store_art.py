"""Arte da Microsoft Store: o produto funcionando sobre uma foto real da camera.

Foto: visita da Ciri ao pote de racao em 2026-10-03. Zona e deteccao sao as
reais (poligono salvo no banco e caixa do YOLOX do proprio app, 94%).
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(r"C:\MonitoraPet")
sys.path.insert(0, str(ROOT / "desktop"))
from make_icons import render  # noqa: E402

PHOTO = ROOT / r"back\app-data\_local-backup-before-prod-20261004-1849\snapshots\2026\10\03\cceb6e16-c413-4944-9dd9-66c5181c742c.jpg"
OUT = ROOT / "desktop" / "dist-store" / "store-assets"
F = r"C:\Windows\Fonts"
BOLD, SEMI, REG = F + r"\segoeuib.ttf", F + r"\seguisb.ttf", F + r"\segoeui.ttf"

ZONE = [(0.6932, 0.5216), (0.6916, 0.9144), (0.9252, 0.9172), (0.9237, 0.5328)]
CAT = (0.7370, 0.3181, 0.9993, 0.8807)
ZONE_FILL, ZONE_STROKE = (221, 141, 49, 30), (255, 189, 102, 255)
GREEN = (82, 107, 69)


def font(path, px):
    return ImageFont.truetype(path, px)


def chip(layer, xy, text, f, fg, bg, dot=None, pad=(0.55, 0.28)):
    d = ImageDraw.Draw(layer)
    b = d.textbbox((0, 0), text, font=f)
    th = f.size
    px, py = int(th * pad[0]), int(th * pad[1])
    dot_w = int(th * 0.9) if dot else 0
    w, h = b[2] - b[0] + 2 * px + dot_w, th + 2 * py
    x, y = xy
    d.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=bg)
    if dot:
        r = th * 0.22
        cx, cy = x + px + r, y + h / 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=dot)
    d.text((x + px + dot_w - b[0], y + (h - (b[3] - b[1])) / 2 - b[1]), text, font=f, fill=fg)
    return w, h


def shadow_under(base, box, radius, blur, alpha=90, dy=0):
    s = Image.new("RGBA", base.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = box
    ImageDraw.Draw(s).rounded_rectangle([x0, y0 + dy, x1, y1 + dy], radius=radius, fill=(8, 14, 6, alpha))
    return Image.alpha_composite(base, s.filter(ImageFilter.GaussianBlur(blur)))


def make(w, h, crop_x0, card_box, k):
    src = Image.open(PHOTO).convert("RGB")
    sw, sh = src.size
    cw = round(sh * w / h)
    # limpeza: tira o ruido da camera antes de ampliar, passa para P&B com
    # tons suaves e escurece as bordas para levar o olho ao centro
    photo = src.crop((crop_x0, 0, crop_x0 + cw, sh)).filter(ImageFilter.MedianFilter(3))
    gray = ImageOps.grayscale(photo)
    gray = ImageOps.autocontrast(gray, cutoff=(0.5, 0.5))
    gray = gray.point(lambda v: round(255 * ((v / 255) ** 0.92)))
    gray = gray.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.8))
    gray = gray.filter(ImageFilter.UnsharpMask(radius=3, percent=55, threshold=4))
    gray = ImageEnhance.Contrast(gray).enhance(1.04)
    photo = ImageOps.colorize(gray, black=(22, 24, 22), white=(250, 250, 247), mid=(132, 136, 131))
    vignette = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vignette).ellipse([-w * 0.25, -h * 0.2, w * 1.25, h * 1.2], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(min(w, h) * 0.18))
    photo = Image.composite(photo, Image.new("RGB", (w, h), (18, 20, 18)), vignette.point(lambda v: 150 + v * 105 // 255))
    img = photo.convert("RGBA")

    def P(nx, ny):
        return ((nx * sw - crop_x0) * w / cw, ny * sh * h / sh)

    # zona de comida, como o app desenha
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    poly = [P(*p) for p in ZONE]
    d.polygon(poly, fill=ZONE_FILL)
    d.line(poly + [poly[0]], fill=ZONE_STROKE, width=int(5 * k), joint="curve")
    img = Image.alpha_composite(img, layer)

    # deteccao: cantos de foco da marca em volta da Ciri
    x0, y0 = P(CAT[0], CAT[1])
    x1, y1 = P(CAT[2], CAT[3])
    x1 = min(x1, w - 14 * k)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    arm, lw = 70 * k, int(8 * k)
    for cx, cy, dx, dy in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
        d.line([(cx + dx * arm, cy), (cx, cy), (cx, cy + dy * arm)], fill=(255, 255, 255, 240), width=lw, joint="curve")
    img = Image.alpha_composite(img, layer)

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    f_chip = font(SEMI, int(34 * k))
    cw_, ch_ = chip(layer, (0, -999), "Ciri · gato 94%", f_chip, (255, 255, 255), GREEN + (255,))
    chip(layer, (min(x0, w - cw_ - 24 * k), y0 - ch_ - 14 * k), "Ciri · gato 94%", f_chip, (255, 255, 255), GREEN + (255,))
    zx, zy = poly[0]
    chip(layer, (zx + 12 * k, zy + 12 * k), "Comida", font(SEMI, int(28 * k)), (92, 60, 20), (255, 236, 205, 245))
    chip(layer, (40 * k, 40 * k), "AO VIVO", font(BOLD, int(28 * k)), (255, 255, 255), (20, 24, 18, 170), dot=(255, 80, 70))
    img = Image.alpha_composite(img, layer)

    # notificacao do app, no estilo de um aviso do Windows
    bx0, by0, bx1, by1 = card_box
    rad = int(30 * k)
    img = shadow_under(img, card_box, rad, 34 * k, alpha=110, dy=int(12 * k))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(card_box, radius=rad, fill=(255, 255, 255, 246))
    pad = int(36 * k)
    logo = render(int(40 * k))
    layer.alpha_composite(logo, (int(bx0 + pad), int(by0 + pad)))
    small = font(REG, int(27 * k))
    d.text((bx0 + pad + 54 * k, by0 + pad + 20 * k), "Monitora Pet  ·  agora", font=small, fill=(110, 118, 106), anchor="lm")
    ty = by0 + pad + 40 * k + 30 * k
    d.text((bx0 + pad, ty), "Ciri está comendo", font=font(BOLD, int(48 * k)), fill=(28, 34, 25), anchor="lt")
    d.text((bx0 + pad, ty + 68 * k), "Pote de ração  ·  há 2 min", font=font(REG, int(33 * k)), fill=(86, 96, 80), anchor="lt")
    img = Image.alpha_composite(img, layer)
    return img.convert("RGB")


k = 1.15
make(1440, 2160, 2304 - 864, (100 * k, 150 * k, 1440 - 100 * k, 150 * k + 252 * k), k).save(OUT / "MonitoraPet_poster_1440x2160.png")
k = 1.5
make(2160, 2160, 2304 - 1296, (110 * k, 150 * k, 110 * k + 640 * k, 150 * k + 252 * k), k).save(OUT / "MonitoraPet_box_2160x2160.png")
print("ok")
