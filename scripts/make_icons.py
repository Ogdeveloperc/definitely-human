"""Render the Definitely Human app icon (DH + green check) to PNG and Windows .ico."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
GREEN, INK = (26, 127, 82), (17, 20, 24)
S = 1024


def stroke(d, pts, w, fill):
    d.line(pts, fill=fill, width=w, joint="curve")
    for x, y in (pts[0], pts[-1]):
        d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=fill)


def render(small=False):
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([24, 24, S - 24, S - 24], radius=230, fill=(255, 255, 255), outline=(222, 226, 230), width=10)
    if small:  # 16-32 px: letters don't survive, the check does
        stroke(d, [(250, 540), (430, 720), (790, 300)], 150, GREEN)
        return im
    f = ImageFont.truetype(str(ROOT / "assets/fonts/Outfit-Variable.ttf"), 470)
    f.set_variation_by_axes([800])
    d.text((S / 2 - 30, 440), "DH", font=f, fill=INK, anchor="mm")
    # badge with check, bottom-right, overlapping the edge of the H like the logo's tick
    cx, cy, r = 770, 770, 165
    d.ellipse([cx - r - 22, cy - r - 22, cx + r + 22, cy + r + 22], fill=(255, 255, 255))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GREEN)
    stroke(d, [(cx - 82, cy + 4), (cx - 22, cy + 64), (cx + 86, cy - 60)], 50, (255, 255, 255))
    return im


big, small = render(), render(small=True)
big.save(OUT / "icon-1024.png")
sizes = [16, 24, 32, 48, 64, 128, 256]
frames = [(small if s <= 32 else big).resize((s, s), Image.LANCZOS) for s in sizes]
frames[-1].save(OUT / "icon.ico", format="ICO", sizes=[(s, s) for s in sizes], append_images=frames[:-1])
big.resize((192, 192), Image.LANCZOS).save(OUT / "icon-192.png")
small.resize((64, 64), Image.LANCZOS).save(OUT / "favicon.png")
print("ok")
