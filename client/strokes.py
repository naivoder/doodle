import pygame

from .constants import STROKE_HIT_TOLERANCE
from .geometry import point_to_segment_dist_sq


class StrokeStore:

    def __init__(self):
        self.strokes = []
        self._dirty = True
        self._surface = None

    def add(self, stroke):
        self.strokes.append({
            "color": tuple(stroke["color"]),
            "points": stroke["points"],
            "width": stroke.get("width", 4),
            "name": stroke.get("name", ""),
        })
        self._dirty = True

    def clear(self):
        self.strokes.clear()
        self._dirty = True

    def mark_dirty(self):
        self._dirty = True

    def render(self, screen_w, screen_h, scale, offset):
        if not self._dirty and self._surface is not None:
            if self._surface.get_size() == (screen_w, screen_h):
                return self._surface

        surf = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        ox, oy = offset
        for s in self.strokes:
            pts = s["points"]
            sw = max(round(s["width"] * scale), 1)
            screen_pts = [(int(p[0] * scale + ox), int(p[1] * scale + oy)) for p in pts]
            color = s["color"]
            if len(screen_pts) == 1:
                pygame.draw.circle(surf, color, screen_pts[0], max(sw // 2, 1))
            elif len(screen_pts) >= 2:
                pygame.draw.lines(surf, color, False, screen_pts, sw)
        self._surface = surf
        self._dirty = False
        return surf

    def render_live(self, surface, points, color, width, scale, offset):
        if len(points) < 2:
            return
        ox, oy = offset
        sw = max(round(width * scale), 1)
        screen_pts = [(int(p[0] * scale + ox), int(p[1] * scale + oy)) for p in points]
        pygame.draw.lines(surface, tuple(color), False, screen_pts, sw)

    def hit_test(self, cx, cy):
        for s in reversed(self.strokes):
            pts = s["points"]
            eff_sq = (STROKE_HIT_TOLERANCE + s["width"] / 2) ** 2
            if len(pts) == 1:
                dx = cx - pts[0][0]
                dy = cy - pts[0][1]
                if dx * dx + dy * dy <= eff_sq:
                    return s["name"]
            else:
                for i in range(len(pts) - 1):
                    d2 = point_to_segment_dist_sq(
                        cx, cy, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]
                    )
                    if d2 <= eff_sq:
                        return s["name"]
        return None
