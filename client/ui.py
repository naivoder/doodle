"""Frosted-glass UI widgets for the doodle client."""

from __future__ import annotations

import math

import pygame

from .constants import (
    COLOR_PICKER_COLUMNS, COLOR_SWATCH_SIZE, GLASS_BG, GLASS_BORDER,
    GLASS_HIGHLIGHT, GLASS_TEXT, ICON_SIZE, PICKER_COLORS, THICKNESS_OPTIONS,
    TOOLTIP_BG, UI_CORNER_RADIUS, UI_FONT_SIZE, UI_PADDING,
)

type ColorHitbox = tuple[pygame.Rect, list[int]]
type ThicknessHitbox = tuple[pygame.Rect, int]


class GlassUI:
    """Frosted-glass style UI widgets rendered as translucent overlays."""

    def __init__(self) -> None:
        self.font: pygame.font.Font | None = None
        self.small_font: pygame.font.Font | None = None

    def init_fonts(self) -> None:
        self.font = pygame.font.SysFont("Helvetica,Arial,sans-serif", UI_FONT_SIZE)
        self.small_font = pygame.font.SysFont("Helvetica,Arial,sans-serif", UI_FONT_SIZE - 2)

    def _panel(self, target: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw a glass panel background with highlight edge."""
        panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(panel, GLASS_BG, panel.get_rect(), border_radius=UI_CORNER_RADIUS)
        pygame.draw.rect(panel, GLASS_BORDER, panel.get_rect(), width=1, border_radius=UI_CORNER_RADIUS)
        hl = pygame.Rect(4, 2, rect.width - 8, 1)
        pygame.draw.rect(panel, GLASS_HIGHLIGHT, hl, border_radius=1)
        target.blit(panel, rect.topleft)

    def draw_tooltip(self, target: pygame.Surface, text: str, pos: tuple[int, int]) -> None:
        surf = self.small_font.render(text, True, (255, 255, 255))
        tw, th = surf.get_size()
        pad = 6
        sw, sh = target.get_size()
        tx = min(pos[0] + 14, sw - tw - pad * 2 - 4)
        ty = max(pos[1] - th - pad * 2 - 4, 4)
        bg = pygame.Surface((tw + pad * 2, th + pad * 2), pygame.SRCALPHA)
        pygame.draw.rect(bg, TOOLTIP_BG, bg.get_rect(), border_radius=8)
        target.blit(bg, (tx, ty))
        target.blit(surf, (tx + pad, ty + pad))

    def draw_user_count(self, target: pygame.Surface, count: int) -> None:
        """Render the active user count badge in the top-right corner."""
        label = f"{count} user{'s' if count != 1 else ''} online"
        text_surf = self.font.render(label, True, GLASS_TEXT)
        tw, th = text_surf.get_size()
        pw = tw + UI_PADDING * 2
        ph = th + UI_PADDING
        sw, _ = target.get_size()
        px = sw - pw - UI_PADDING
        py = UI_PADDING
        rect = pygame.Rect(px, py, pw, ph)
        self._panel(target, rect)
        target.blit(text_surf, (px + UI_PADDING, py + UI_PADDING // 2))

    # --- Color picker ---

    def draw_color_icon(self, target: pygame.Surface, color: list[int], pos: tuple[int, int]) -> pygame.Rect:
        rect = pygame.Rect(pos[0], pos[1], ICON_SIZE, ICON_SIZE)
        self._panel(target, rect)
        pygame.draw.rect(target, tuple(color), rect.inflate(-8, -8), border_radius=6)
        return rect

    def draw_color_panel(
        self, target: pygame.Surface, current_color: list[int], anchor: tuple[int, int],
    ) -> tuple[list[ColorHitbox], pygame.Rect]:
        cols = COLOR_PICKER_COLUMNS
        rows = math.ceil(len(PICKER_COLORS) / cols)
        swatch, gap = COLOR_SWATCH_SIZE, 4
        inner_w = cols * (swatch + gap) - gap
        inner_h = rows * (swatch + gap) - gap
        pw = inner_w + UI_PADDING * 2
        ph = inner_h + UI_PADDING * 2
        px, py = anchor[0], anchor[1] - ph - 6

        rect = pygame.Rect(px, py, pw, ph)
        self._panel(target, rect)

        hitboxes: list[ColorHitbox] = []
        bx, by = px + UI_PADDING, py + UI_PADDING
        for i, color in enumerate(PICKER_COLORS):
            c, r = i % cols, i // cols
            sr = pygame.Rect(bx + c * (swatch + gap), by + r * (swatch + gap), swatch, swatch)
            pygame.draw.rect(target, tuple(color), sr, border_radius=4)
            if color == list(current_color):
                pygame.draw.rect(target, (255, 255, 255), sr.inflate(4, 4), width=2, border_radius=6)
            hitboxes.append((sr, color))
        return hitboxes, rect

    # --- Thickness picker ---

    def draw_thickness_icon(
        self, target: pygame.Surface, width: int, color: list[int], pos: tuple[int, int],
    ) -> pygame.Rect:
        rect = pygame.Rect(pos[0], pos[1], ICON_SIZE, ICON_SIZE)
        self._panel(target, rect)
        r = max(min(width, ICON_SIZE - 10) // 2, 2)
        pygame.draw.circle(target, tuple(color), rect.center, r)
        return rect

    def draw_thickness_panel(
        self, target: pygame.Surface, current_width: int, color: list[int], anchor: tuple[int, int],
    ) -> tuple[list[ThicknessHitbox], pygame.Rect]:
        count = len(THICKNESS_OPTIONS)
        cell = ICON_SIZE + 4
        pw = count * cell + UI_PADDING * 2 - 4
        ph = cell + UI_PADDING * 2 - 4
        px, py = anchor[0], anchor[1] - ph - 6

        rect = pygame.Rect(px, py, pw, ph)
        self._panel(target, rect)

        hitboxes: list[ThicknessHitbox] = []
        bx, by = px + UI_PADDING, py + UI_PADDING
        for i, w in enumerate(THICKNESS_OPTIONS):
            sr = pygame.Rect(bx + i * cell, by, ICON_SIZE, ICON_SIZE)
            r = max(min(w, ICON_SIZE - 6) // 2, 2)
            pygame.draw.circle(target, tuple(color), sr.center, r)
            if w == current_width:
                pygame.draw.rect(target, (255, 255, 255), sr.inflate(2, 2), width=2, border_radius=8)
            hitboxes.append((sr, w))
        return hitboxes, rect
