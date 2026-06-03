import base64
import os
import random
import struct

from PIL import Image

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"}


def load_image(path):
    img = Image.open(path)
    w, h = img.size
    with open(path, "rb") as f:
        raw = f.read()
    b64 = base64.b64encode(raw).decode("ascii")
    return b64, w, h


def discover_images(path):
    if os.path.isfile(path):
        return [path]
    entries = [
        os.path.join(path, e)
        for e in os.listdir(path)
        if os.path.splitext(e)[1].lower() in IMAGE_EXTS
    ]
    random.shuffle(entries)
    return entries
