import io

import pygame

from .geometry import scale_to_fit
from .strokes import StrokeStore


class ClientState:

    def __init__(self):
        self.screen = None
        self.base_surface = None
        self.scale_factor = 1.0
        self.img_offset = (0, 0)
        self.native_w = 0
        self.native_h = 0
        self._raw_image = None

        self.my_color = [255, 255, 255]
        self.my_name = ""
        self.my_id = 0
        self.brush_width = 4
        self.drawing = False
        self.current_stroke_points = []
        self.users = []
        self.running = True

        self.strokes = StrokeStore()

        self.color_icon_rect = pygame.Rect(0, 0, 0, 0)
        self.color_panel_rect = pygame.Rect(0, 0, 0, 0)
        self.color_hitboxes = []
        self.color_expanded = False

        self.thick_icon_rect = pygame.Rect(0, 0, 0, 0)
        self.thick_panel_rect = pygame.Rect(0, 0, 0, 0)
        self.thick_hitboxes = []
        self.thick_expanded = False

        self.hover_name = None

    def _compute_layout(self):
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

    def _rebuild_base(self):
        if self._raw_image is None:
            return
        sf = self.scale_factor
        if sf == 1.0:
            self.base_surface = self._raw_image
        else:
            dw = int(self.native_w * sf)
            dh = int(self.native_h * sf)
            self.base_surface = pygame.transform.smoothscale(self._raw_image, (dw, dh))

    def set_image(self, w, h, image_bytes):
        self._raw_image = pygame.image.load(io.BytesIO(image_bytes))
        self.native_w, self.native_h = w, h
        self._compute_layout()
        self._rebuild_base()
        self.strokes.mark_dirty()

    def handle_resize(self, new_w, new_h):
        self.screen = pygame.display.set_mode((new_w, new_h), pygame.RESIZABLE | pygame.SCALED)
        if self.native_w > 0:
            self._compute_layout()
            self._rebuild_base()
            self.strokes.mark_dirty()

    def screen_to_canvas(self, pos):
        return (
            int((pos[0] - self.img_offset[0]) / self.scale_factor),
            int((pos[1] - self.img_offset[1]) / self.scale_factor),
        )

    def any_ui_hit(self, pos):
        if self.color_icon_rect.collidepoint(pos):
            return True
        if self.color_expanded and self.color_panel_rect.collidepoint(pos):
            return True
        if self.thick_icon_rect.collidepoint(pos):
            return True
        if self.thick_expanded and self.thick_panel_rect.collidepoint(pos):
            return True
        return False

    def is_on_canvas(self, pos):
        if self.any_ui_hit(pos):
            return False
        x, y = pos
        ox, oy = self.img_offset
        sf = self.scale_factor
        return ox <= x < ox + self.native_w * sf and oy <= y < oy + self.native_h * sf
