"""Tests for ClientState: image handling, coordinate conversion, and UI hit detection."""

import pygame
import pytest

from tests.conftest import make_png_bytes
from client.state import ClientState


@pytest.fixture
def client_state():
    """A ClientState with a small dummy display."""
    st = ClientState()
    st.screen = pygame.display.set_mode((800, 600), pygame.NOFRAME)
    return st


@pytest.fixture
def client_with_image(client_state):
    """A ClientState with an image loaded."""
    client_state.set_image(100, 100, make_png_bytes(100, 100))
    return client_state


class TestSetImage:
    def test_sets_native_dimensions(self, client_state):
        client_state.set_image(200, 150, make_png_bytes(200, 150))
        assert client_state.native_w == 200
        assert client_state.native_h == 150

    def test_creates_base_surface(self, client_state):
        client_state.set_image(100, 100, make_png_bytes(100, 100))
        assert client_state.base_surface is not None

    def test_marks_strokes_dirty(self, client_state):
        client_state.strokes._dirty = False
        client_state.set_image(100, 100, make_png_bytes(100, 100))
        assert client_state.strokes._dirty is True


class TestComputeLayout:
    def test_small_image_scale_is_one(self, client_state):
        """Images smaller than the screen should not be scaled up."""
        client_state.set_image(100, 100, make_png_bytes(100, 100))
        assert client_state.scale_factor == 1.0

    def test_large_image_scaled_down(self, client_state):
        """Images larger than the screen should be scaled to fit."""
        client_state.set_image(1600, 1200, make_png_bytes(4, 3))
        assert client_state.scale_factor < 1.0

    def test_image_centered(self, client_state):
        """A small image should be centered in the window."""
        client_state.set_image(100, 100, make_png_bytes(100, 100))
        ox, oy = client_state.img_offset
        assert ox == (800 - 100) // 2
        assert oy == (600 - 100) // 2


class TestScreenToCanvas:
    def test_identity_at_scale_one(self, client_with_image):
        ox, oy = client_with_image.img_offset
        result = client_with_image.screen_to_canvas((ox + 50, oy + 50))
        assert abs(result[0] - 50) < 1
        assert abs(result[1] - 50) < 1

    def test_accounts_for_offset(self, client_with_image):
        ox, oy = client_with_image.img_offset
        result = client_with_image.screen_to_canvas((ox, oy))
        assert abs(result[0]) < 1
        assert abs(result[1]) < 1


class TestIsOnCanvas:
    def test_center_of_image_is_on_canvas(self, client_with_image):
        ox, oy = client_with_image.img_offset
        assert client_with_image.is_on_canvas((ox + 50, oy + 50))

    def test_outside_image_not_on_canvas(self, client_with_image):
        assert not client_with_image.is_on_canvas((0, 0))

    def test_no_image_not_on_canvas(self, client_state):
        """With no image loaded (native_w=0), nothing is on canvas."""
        assert not client_state.is_on_canvas((400, 300))


class TestAnyUiHit:
    def test_no_hit_by_default(self, client_state):
        assert not client_state.any_ui_hit((400, 300))

    def test_hit_color_icon(self, client_state):
        client_state.color_icon_rect = pygame.Rect(10, 560, 32, 32)
        assert client_state.any_ui_hit((20, 570))

    def test_hit_expanded_color_panel(self, client_state):
        client_state.color_expanded = True
        client_state.color_panel_rect = pygame.Rect(10, 400, 200, 150)
        assert client_state.any_ui_hit((100, 450))

    def test_collapsed_panel_not_hit(self, client_state):
        client_state.color_expanded = False
        client_state.color_panel_rect = pygame.Rect(10, 400, 200, 150)
        assert not client_state.any_ui_hit((100, 450))


class TestHandleResize:
    def test_recalculates_layout_on_new_screen_size(self, client_with_image):
        """Simulate resize by swapping the screen and re-running layout logic."""
        old_offset = client_with_image.img_offset
        client_with_image.screen = pygame.Surface((1024, 768))
        client_with_image._compute_layout()
        client_with_image._rebuild_base()
        new_offset = client_with_image.img_offset
        assert new_offset != old_offset
        # Image should be re-centered for the new dimensions
        ox, oy = new_offset
        assert ox == (1024 - 100) // 2
        assert oy == (768 - 100) // 2
