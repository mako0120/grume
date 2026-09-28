from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()


def normalize_image(src: str | Path, dst_dir: str | Path, max_side: int = 2400) -> Path:
    src = Path(src)
    dst_dir = Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{src.stem}.jpg"

    with Image.open(src) as image:
        image = ImageOps.exif_transpose(image)
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        image.save(dst, "JPEG", quality=92, optimize=True)

    return dst
