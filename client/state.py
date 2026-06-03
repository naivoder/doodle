"""All mutable client-side state: image, drawing, and UI panels."""

from __future__ import annotations

import io

import pygame

from .geometry import scale_to_fit
from .strokes import StrokeStore
from .ui import ColorHitbox, ThicknessHitbox


class ClientState:
    """Owns the display surface, image data, stroke store, and UI state."""

    def __init__(self) -> None:
        self.screen: pygame.Surface | None = None
        self.base_surface: pygame.Surface | None = None
        self.scale_factor: float = 1.0
        self.img_offset: tuple[int, int] = (0, 0)
        self.native_w: int = 0
        self.native_h: int = 0
        self._raw_image: pygame.Surface | None = None

        self.my_color: list[int] = [255, 255, 255]
        self.my_name: str = ""
        self.my_id: int = 0
        self.brush_width: int = 4
        self.drawing: bool = False
        self.current_stroke_points: list[list[float]] = []
        self.users: list[dict] = []
        self.running: bool = True

        self.strokes: StrokeStore = StrokeStore()

        self.color_icon_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.color_panel_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.color_hitboxes: list[ColorHitbox] = []
        self.color_expanded: bool = False

        self.thick_icon_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.thick_panel_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.thick_hitboxes: list[ThicknessHitbox] = []
        self.thick_expanded: bool = False

        self.hover_name: str | None = None

    def _compute_layout(self) -> None:
        sw, sh = self.screen.get_size()
        nw, nh = self.native_w, self.native_h
        if nw <= sw and nh <= sh:
            self.scale_factor = 1.0
        else:
            fit_w, _ = scale_to_fit(nw, nh, sw, sh)
            self.scale_factor = fit_w / nw
        dw = int(nw * self.scale_factor)
        dh = int(nh * self.scale_factor)
        self.img_offset = ((sw - dw) // 2, (sh - dh) // 2)

    def _rebuild_base(self) -> None:
        """Scale the raw image for the current layout."""
        if self._raw_image is None:
            return
        sf = self.scale_factor
        if sf == 1.0:
            self.base_surface = self._raw_image
        else:
            dw = int(self.native_w * sf)
            dh = int(self.native_h * sf)
            self.base_surface = pygame.transform.smoothscale(self._raw_image, (dw, dh))

    def set_image(self, w: int, h: int, image_bytes: bytes) -> None:
        self._raw_image = pygame.image.load(io.BytesIO(image_bytes))
        self.native_w, self.native_h = w, h
        self._compute_layout()
        self._rebuild_base()
        self.strokes.mark_dirty()

    def handle_resize(self, new_w: int, new_h: int) -> None:
        self.screen = pygame.display.set_mode((new_w, new_h), pygame.RESIZABLE | pygame.SCALED)
        if self.native_w > 0:
            self._compute_layout()
            self._rebuild_base()
            self.strokes.mark_dirty()

    def screen_to_canvas(self, pos: tuple[int, int]) -> list[float]:
        """Convert a screen pixel position to canvas (native image) coordinates."""
        return [
            (pos[0] - self.img_offset[0]) / self.scale_factor,
            (pos[1] - self.img_offset[1]) / self.scale_factor,
        ]

    def any_ui_hit(self, pos: tuple[int, int]) -> bool:
        if self.color_icon_rect.collidepoint(pos):
            return True
        if self.color_expanded and self.color_panel_rect.collidepoint(pos):
            return True
        if self.thick_icon_rect.collidepoint(pos):
            return True
        if self.thick_expanded and self.thick_panel_rect.collidepoint(pos):
            return True
        return False

    def is_on_canvas(self, pos: tuple[int, int]) -> bool:
        """True if pos is inside the image area and not over any UI element."""
        if self.any_ui_hit(pos):
            return False
        x, y = pos
        ox, oy = self.img_offset
        sf = self.scale_factor
        return ox <= x < ox + self.native_w * sf and oy <= y < oy + self.native_h * sf
