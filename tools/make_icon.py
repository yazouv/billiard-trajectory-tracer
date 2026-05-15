"""Génère assets/icon.ico (logo CAB Replay : 3 billes sur tapis vert).

Usage : py tools/make_icon.py
"""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
OUT.parent.mkdir(parents=True, exist_ok=True)


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    margin = max(2, size // 32)
    radius = size // 6
    # Tapis : carré arrondi vert foncé avec bord plus clair
    d.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius, fill=(20, 105, 60, 255),
        outline=(255, 255, 255, 60), width=max(1, size // 48),
    )

    # Trois billes : blanc, jaune, rouge
    r = size * 0.18
    cx, cy = size / 2, size / 2
    offset = size * 0.22
    balls = [
        (cx, cy - offset, (255, 255, 255, 255)),
        (cx - offset * 0.95, cy + offset * 0.55, (240, 198, 0, 255)),
        (cx + offset * 0.95, cy + offset * 0.55, (215, 40, 40, 255)),
    ]
    for x, y, color in balls:
        d.ellipse([x - r, y - r, x + r, y + r],
                  fill=color, outline=(0, 0, 0, 200), width=max(1, size // 64))
        # Petit reflet
        rr = r * 0.32
        d.ellipse([x - rr - r * 0.25, y - rr - r * 0.25,
                   x + rr - r * 0.25, y + rr - r * 0.25],
                  fill=(255, 255, 255, 110))
    return img


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base = render(256)
    base.save(OUT, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"Écrit : {OUT}  ({OUT.stat().st_size} octets)")


if __name__ == "__main__":
    main()
