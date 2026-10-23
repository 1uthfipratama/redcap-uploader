"""Make the app's icons from one PNG: the window icon, the Windows .ico and the macOS .icns.

    python -m tools.make_icons SOURCE.png

The picture is cropped to what is drawn, centred on a square, and written to app/assets/brand/,
where config/brand.yaml and the installers look for it. Export the source at 1024 px or more:
a small source makes blurry large icons.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "app" / "assets" / "brand"
ICO_SIZES = [(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)]
MARGIN = 0.04  # space around the drawing, as a share of its longer side
SHARP = 256  # sources smaller than this make soft large icons


def square(image: Image.Image) -> Image.Image:
    """The drawn part of the picture, centred on a transparent square."""
    image = image.convert("RGBA")
    image = image.crop(image.getchannel("A").getbbox() or (0, 0, *image.size))
    side = round(max(image.size) * (1 + 2 * MARGIN))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2), image)
    return canvas


def main(argv: list[str] | None = None) -> None:
    source = Path((sys.argv[1:] if argv is None else argv)[0])
    icon = square(Image.open(source))
    OUT.mkdir(parents=True, exist_ok=True)
    icon.save(OUT / "icon.png")
    icon.resize((256, 256), Image.LANCZOS).save(OUT / "icon.ico", sizes=ICO_SIZES)
    icon.resize((1024, 1024), Image.LANCZOS).save(OUT / "icon.icns")
    print(f"wrote icon.png, icon.ico and icon.icns to {OUT}")
    if icon.width < SHARP:
        print(f"note: the source is {icon.width} px wide; export it at 1024 px for sharp large icons")


if __name__ == "__main__":
    main()
