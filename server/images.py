"""Image loading and discovery for the slideshow server."""

import base64
import os
import random

from PIL import Image
from typing import Final

IMAGE_EXTS: Final[set[str]] = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"}


def load_image(path: str) -> tuple[str, int, int]:
    """Return (base64_data, width, height) for the image at ``path``."""
    img = Image.open(path)
    w, h = img.size
    with open(path, "rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode("ascii")
    return b64, w, h


def discover_images(path: str) -> list[str]:
    """Find supported image files at ``path``. Returns a shuffled list."""
    if os.path.isfile(path):
        return [path]
    entries = [
        os.path.join(path, e)
        for e in os.listdir(path)
        if os.path.splitext(e)[1].lower() in IMAGE_EXTS
    ]
    random.shuffle(entries)
    return entries
