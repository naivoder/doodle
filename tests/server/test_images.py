"""Tests for image loading and discovery."""

import base64
import os

from tests.conftest import make_png_bytes
from server.images import IMAGE_EXTS, discover_images, load_image


class TestLoadImage:
    def test_returns_base64_and_dimensions(self, tmp_png):
        b64, w, h = load_image(tmp_png)
        assert w == 4
        assert h == 4
        raw = base64.b64decode(b64)
        assert raw[:4] == b"\x89PNG"

    def test_roundtrips_original_bytes(self, tmp_png):
        b64, _, _ = load_image(tmp_png)
        decoded = base64.b64decode(b64)
        with open(tmp_png, "rb") as f:
            assert decoded == f.read()


class TestDiscoverImages:
    def test_single_file_returns_list_of_one(self, tmp_png):
        result = discover_images(tmp_png)
        assert result == [tmp_png]

    def test_directory_finds_all_pngs(self, tmp_image_dir):
        result = discover_images(tmp_image_dir)
        assert len(result) == 3
        assert all(f.endswith(".png") for f in result)

    def test_ignores_non_image_files(self, tmp_image_dir):
        result = discover_images(tmp_image_dir)
        assert not any("notes.txt" in f for f in result)

    def test_returns_absolute_paths(self, tmp_image_dir):
        result = discover_images(tmp_image_dir)
        assert all(os.path.isabs(f) for f in result)

    def test_supported_extensions_are_comprehensive(self):
        expected = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"}
        assert IMAGE_EXTS == expected
