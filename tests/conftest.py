"""Shared fixtures for the doodle test suite."""

from __future__ import annotations

import asyncio
import base64
import os
import struct
import tempfile
from collections import deque
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pygame
import pytest

from server.state import ServerState


@pytest.fixture(scope="session", autouse=True)
def _init_pygame():
    """Initialize pygame once for the entire test session with a dummy display."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


def make_png_bytes(width: int = 2, height: int = 2) -> bytes:
    """Create a minimal valid PNG file in memory."""
    import zlib

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        raw = chunk_type + data
        return struct.pack(">I", len(data)) + raw + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)

    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw_rows = b""
    for _ in range(height):
        raw_rows += b"\x00" + b"\xff\x00\x00" * width  # filter byte + red pixels
    idat_data = zlib.compress(raw_rows)

    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr_data)
        + _chunk(b"IDAT", idat_data)
        + _chunk(b"IEND", b"")
    )


@pytest.fixture
def tmp_png(tmp_path) -> str:
    """Write a tiny PNG to a temp directory and return its path."""
    path = tmp_path / "test.png"
    path.write_bytes(make_png_bytes(4, 4))
    return str(path)


@pytest.fixture
def tmp_image_dir(tmp_path) -> str:
    """Create a temp directory with several PNGs."""
    for name in ("a.png", "b.png", "c.png"):
        (tmp_path / name).write_bytes(make_png_bytes(4, 4))
    # Non-image file should be ignored
    (tmp_path / "notes.txt").write_text("not an image")
    return str(tmp_path)


@pytest.fixture
def server_state(tmp_png) -> ServerState:
    """A ServerState initialized with a single test image."""
    state = ServerState([tmp_png], "cut", 60)
    state.load_current_image()
    return state


@pytest.fixture
def multi_image_state(tmp_image_dir) -> ServerState:
    """A ServerState with multiple images for slideshow testing."""
    from server.images import discover_images
    images = discover_images(tmp_image_dir)
    state = ServerState(images, "cut", 10)
    state.load_current_image()
    return state


def make_mock_ws() -> AsyncMock:
    """Create a mock ServerConnection with send() and remote_address."""
    ws = AsyncMock()
    ws.remote_address = ("127.0.0.1", 9999)
    ws.send = AsyncMock()
    return ws
