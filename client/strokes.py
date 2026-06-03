"""Canvas stroke storage, rendering, and hit-testing."""

from __future__ import annotations

from typing import Any

import pygame
from pydantic import BaseModel

from .constants import STROKE_HIT_TOLERANCE
from .geometry import point_to_segment_dist_sq


class Stroke(BaseModel):
    """Single completed stroke in canvas (native-image) coordinates."""
    color: tuple[int, int, int]
    points: list[list[float]]
    width: int = 4
    name: str = ""


class StrokeStore:
    """Stores strokes in canvas coords, renders them in screen space.

    Maintains a cached surface that is only re-rendered when dirty.
    """

    def __init__(self) -> None:
        self.strokes: list[Stroke] = []
        self._dirty: bool = True
        self._surface: pygame.Surface | None = None

    def add(self, raw: dict[str, Any]) -> None:
        """Append a stroke from a raw message dict."""
        self.strokes.append(Stroke(
            color=tuple(raw["color"]),
            points=raw["points"],
            width=raw.get("width", 4),
            name=raw.get("name", ""),
        ))
        self._dirty = True

    def clear(self) -> None:
        self.strokes.clear()
        self._dirty = True

    def mark_dirty(self) -> None:
        self._dirty = True

    def render(self, screen_w: int, screen_h: int, scale: float, offset: tuple[int, int]) -> pygame.Surface:
        """Return an SRCALPHA surface with all strokes projected to screen space."""
        if not self._dirty and self._surface is not None:
            if self._surface.get_size() == (screen_w, screen_h):
                return self._surface

        surf = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
        ox, oy = offset
        for s in self.strokes:
            sw = max(round(s.width * scale), 1)
            screen_pts = [(int(p[0] * scale + ox), int(p[1] * scale + oy)) for p in s.points]
            if len(screen_pts) == 1:
                pygame.draw.circle(surf, s.color, screen_pts[0], max(sw // 2, 1))
            elif len(screen_pts) >= 2:
                pygame.draw.lines(surf, s.color, False, screen_pts, sw)
        self._surface = surf
        self._dirty = False
        return surf

    def render_live(
        self, surface: pygame.Surface, points: list[list[float]], color: list[int],
        width: int, scale: float, offset: tuple[int, int],
    ) -> None:
        """Draw an in-progress stroke directly (no caching)."""
        if len(points) < 2:
            return
        ox, oy = offset
        sw = max(round(width * scale), 1)
        screen_pts = [(int(p[0] * scale + ox), int(p[1] * scale + oy)) for p in points]
        pygame.draw.lines(surface, tuple(color), False, screen_pts, sw)

    def hit_test(self, cx: float, cy: float) -> str | None:
        """Return the name of the topmost stroke near canvas point, or None."""
        for s in reversed(self.strokes):
            eff_sq = (STROKE_HIT_TOLERANCE + s.width / 2) ** 2
            if len(s.points) == 1:
                dx = cx - s.points[0][0]
                dy = cy - s.points[0][1]
                if dx * dx + dy * dy <= eff_sq:
                    return s.name
            else:
                for i in range(len(s.points) - 1):
                    d2 = point_to_segment_dist_sq(
                        cx, cy,
                        s.points[i][0], s.points[i][1],
                        s.points[i + 1][0], s.points[i + 1][1],
                    )
                    if d2 <= eff_sq:
                        return s.name
        return None
