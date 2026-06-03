import math

import pygame

from .constants import (
    COLOR_PICKER_COLUMNS, COLOR_SWATCH_SIZE, GLASS_BG, GLASS_BORDER,
    GLASS_HIGHLIGHT, GLASS_TEXT, ICON_SIZE, PICKER_COLORS, THICKNESS_OPTIONS,
    TOOLTIP_BG, UI_CORNER_RADIUS, UI_FONT_SIZE, UI_PADDING,
)


class GlassUI:

    def __init__(self):
        self.font = None
        self.small_font = None

    def init_fonts(self):
        self.font = pygame.font.SysFont("Helvetica,Arial,sans-serif", UI_FONT_SIZE)
        self.small_font = pygame.font.SysFont("Helvetica,Arial,sans-serif", UI_FONT_SIZE - 2)

    def _panel(self, target, rect):
        panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(panel, GLASS_BG, panel.get_rect(), border_radius=UI_CORNER_RADIUS)
        pygame.draw.rect(panel, GLASS_BORDER, panel.get_rect(), width=1, border_radius=UI_CORNER_RADIUS)
        hl = pygame.Rect(4, 2, rect.width - 8, 1)
        pygame.draw.rect(panel, GLASS_HIGHLIGHT, hl, border_radius=1)
        target.blit(panel, rect.topleft)

    # --- Tooltip ---

    def draw_tooltip(self, target, text, pos):
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

    # --- User count badge ---

    def draw_user_count(self, target, count):
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

    def draw_color_icon(self, target, color, pos):
        rect = pygame.Rect(pos[0], pos[1], ICON_SIZE, ICON_SIZE)
        self._panel(target, rect)
        pygame.draw.rect(target, tuple(color), rect.inflate(-8, -8), border_radius=6)
        return rect

    def draw_color_panel(self, target, current_color, anchor):
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

        hitboxes = []
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

    def draw_thickness_icon(self, target, width, color, pos):
        rect = pygame.Rect(pos[0], pos[1], ICON_SIZE, ICON_SIZE)
        self._panel(target, rect)
        r = max(min(width, ICON_SIZE - 10) // 2, 2)
        pygame.draw.circle(target, tuple(color), rect.center, r)
        return rect

    def draw_thickness_panel(self, target, current_width, color, anchor):
        count = len(THICKNESS_OPTIONS)
        cell = ICON_SIZE + 4
        pw = count * cell + UI_PADDING * 2 - 4
        ph = cell + UI_PADDING * 2 - 4
        px, py = anchor[0], anchor[1] - ph - 6

        rect = pygame.Rect(px, py, pw, ph)
        self._panel(target, rect)

        hitboxes = []
        bx, by = px + UI_PADDING, py + UI_PADDING
        for i, w in enumerate(THICKNESS_OPTIONS):
            sr = pygame.Rect(bx + i * cell, by, ICON_SIZE, ICON_SIZE)
            r = max(min(w, ICON_SIZE - 6) // 2, 2)
            pygame.draw.circle(target, tuple(color), sr.center, r)
            if w == current_width:
                pygame.draw.rect(target, (255, 255, 255), sr.inflate(2, 2), width=2, border_radius=8)
            hitboxes.append((sr, w))
        return hitboxes, rect
