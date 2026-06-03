#!/usr/bin/env python3
"""Pygame client for the doodle slideshow server."""

import argparse
import asyncio
import base64
import collections
import io
import json
import math
import sys

import pygame
import websockets

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TARGET_WIDTH = 1280
TARGET_HEIGHT = 960

UI_FONT_SIZE = 14
UI_PADDING = 10
UI_CORNER_RADIUS = 12
COLOR_SWATCH_SIZE = 22
COLOR_PICKER_COLUMNS = 6
ICON_SIZE = 32
THICKNESS_OPTIONS = [2, 4, 6, 10, 16, 24]
STROKE_HIT_TOLERANCE = 8

GLASS_BG = (255, 255, 255, 40)
GLASS_BORDER = (255, 255, 255, 80)
GLASS_TEXT = (255, 255, 255)
GLASS_HIGHLIGHT = (255, 255, 255, 60)
TOOLTIP_BG = (30, 30, 30, 200)

PICKER_COLORS = [
    [231, 76, 60],    [192, 57, 43],    [211, 84, 0],
    [243, 156, 18],   [241, 196, 15],   [39, 174, 96],
    [46, 134, 193],   [41, 128, 185],   [142, 68, 173],
    [26, 188, 156],   [22, 160, 133],   [52, 73, 94],
    [236, 240, 241],  [189, 195, 199],  [127, 140, 141],
    [44, 62, 80],     [255, 255, 255],  [30, 30, 30],
]


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def scale_to_fit(img_w, img_h, target_w, target_h):
    ratio = min(target_w / img_w, target_h / img_h)
    return int(img_w * ratio), int(img_h * ratio)


def point_to_segment_dist_sq(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy
    if len_sq == 0:
        return (px - ax) ** 2 + (py - ay) ** 2
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return (px - proj_x) ** 2 + (py - proj_y) ** 2


# ---------------------------------------------------------------------------
# Stroke storage
#
# Strokes arrive in *canvas* (native image) coordinates from the server.
# We store them that way and convert to screen coords at render time.
# On resize we just re-render — no surface scaling needed.
# ---------------------------------------------------------------------------

class StrokeStore:
    """Stores strokes in canvas coords. Renders them in screen space."""

    def __init__(self):
        self.strokes = []  # [{color, points, width, name}, ...]
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
        """Return an SRCALPHA surface with all strokes in screen space."""
        if not self._dirty and self._surface is not None:
            sz = self._surface.get_size()
            if sz == (screen_w, screen_h):
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
        """Draw an in-progress stroke directly onto a surface (no caching)."""
        if len(points) < 2:
            return
        ox, oy = offset
        sw = max(round(width * scale), 1)
        screen_pts = [(int(p[0] * scale + ox), int(p[1] * scale + oy)) for p in points]
        pygame.draw.lines(surface, tuple(color), False, screen_pts, sw)

    def hit_test(self, cx, cy):
        """Return name of topmost stroke near canvas point (cx, cy), or None."""
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


# ---------------------------------------------------------------------------
# Glassmorphism UI
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Client state
# ---------------------------------------------------------------------------

class ClientState:

    def __init__(self):
        self.screen = None
        self.base_surface = None
        self.scale_factor = 1.0
        self.img_offset = (0, 0)
        self.native_w = 0
        self.native_h = 0
        self._raw_image = None  # unscaled pygame surface for resize

        self.my_color = [255, 255, 255]
        self.my_name = ""
        self.my_id = 0
        self.brush_width = 4
        self.drawing = False
        self.current_stroke_points = []
        self.users = []
        self.running = True

        self.strokes = StrokeStore()

        # UI
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


# ---------------------------------------------------------------------------
# WebSocket reader task
# ---------------------------------------------------------------------------

async def ws_reader(ws, msg_queue, state):
    try:
        async for raw in ws:
            msg_queue.append(json.loads(raw))
    except websockets.ConnectionClosed:
        pass
    finally:
        state.running = False


# ---------------------------------------------------------------------------
# Main client loop
# ---------------------------------------------------------------------------

async def run_client(server_url):
    pygame.init()

    st = ClientState()
    st.screen = pygame.display.set_mode(
        (TARGET_WIDTH, TARGET_HEIGHT), pygame.RESIZABLE | pygame.SCALED
    )
    pygame.display.set_caption("Doodle - Shared Canvas")

    glass = GlassUI()
    glass.init_fonts()
    clock = pygame.time.Clock()
    msg_queue = collections.deque()
    send_queue = collections.deque()

    print(f"Connecting to {server_url} ...")

    try:
        async with websockets.connect(server_url, max_size=20 * 1024 * 1024, close_timeout=2) as ws:
            print("Connected. Waiting for image...")
            reader_task = asyncio.create_task(ws_reader(ws, msg_queue, st))

            try:
                while st.running:
                    mouse_pos = pygame.mouse.get_pos()

                    # --- Pygame events ---
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            st.running = False

                        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                            st.running = False

                        elif event.type == pygame.VIDEORESIZE:
                            st.handle_resize(event.w, event.h)

                        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            if st.color_expanded:
                                clicked = False
                                for sr, color in st.color_hitboxes:
                                    if sr.collidepoint(event.pos):
                                        st.my_color = list(color)
                                        send_queue.append({"type": "color_change", "color": st.my_color})
                                        clicked = True
                                        break
                                if clicked or st.color_panel_rect.collidepoint(event.pos):
                                    continue

                            if st.thick_expanded:
                                clicked = False
                                for sr, w in st.thick_hitboxes:
                                    if sr.collidepoint(event.pos):
                                        st.brush_width = w
                                        clicked = True
                                        break
                                if clicked or st.thick_panel_rect.collidepoint(event.pos):
                                    continue

                            if st.base_surface is not None and st.is_on_canvas(event.pos):
                                st.drawing = True
                                st.current_stroke_points = [st.screen_to_canvas(event.pos)]

                        elif event.type == pygame.MOUSEMOTION and st.drawing:
                            st.current_stroke_points.append(st.screen_to_canvas(event.pos))

                        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                            if st.drawing and st.current_stroke_points:
                                stroke = {
                                    "type": "draw",
                                    "color": st.my_color,
                                    "points": st.current_stroke_points,
                                    "width": st.brush_width,
                                }
                                send_queue.append(stroke)
                                st.strokes.add({
                                    "color": st.my_color,
                                    "points": st.current_stroke_points,
                                    "width": st.brush_width,
                                    "name": st.my_name,
                                })
                            st.drawing = False
                            st.current_stroke_points = []

                    # --- Hover ---
                    st.color_expanded = (
                        st.color_icon_rect.inflate(6, 6).collidepoint(mouse_pos)
                        or (st.color_expanded and st.color_panel_rect.inflate(10, 10).collidepoint(mouse_pos))
                    )
                    st.thick_expanded = (
                        st.thick_icon_rect.inflate(6, 6).collidepoint(mouse_pos)
                        or (st.thick_expanded and st.thick_panel_rect.inflate(10, 10).collidepoint(mouse_pos))
                    )

                    st.hover_name = None
                    if not st.drawing and not st.any_ui_hit(mouse_pos) and st.is_on_canvas(mouse_pos):
                        cx, cy = st.screen_to_canvas(mouse_pos)
                        st.hover_name = st.strokes.hit_test(cx, cy)

                    # --- Process WS messages ---
                    while msg_queue:
                        msg = msg_queue.popleft()
                        mtype = msg["type"]

                        if mtype == "image_sync":
                            st.set_image(msg["width"], msg["height"], base64.b64decode(msg["data"]))
                            print(f"Image loaded: {msg['width']}x{msg['height']}")

                        elif mtype == "transition":
                            st.set_image(msg["width"], msg["height"], base64.b64decode(msg["to_data"]))

                        elif mtype == "color_assign":
                            st.my_color = msg["color"]
                            st.my_name = msg.get("name", "")
                            st.my_id = msg.get("id", 0)

                        elif mtype == "user_list":
                            st.users = msg["users"]

                        elif mtype == "draw_history":
                            for stroke in msg["strokes"]:
                                st.strokes.add(stroke)

                        elif mtype == "draw":
                            st.strokes.add(msg)

                        elif mtype == "clear_doodles":
                            st.strokes.clear()

                    # --- Flush send queue ---
                    while send_queue:
                        try:
                            await ws.send(json.dumps(send_queue.popleft()))
                        except websockets.ConnectionClosed:
                            st.running = False
                            break

                    # --- Render ---
                    st.screen.fill((20, 20, 25))

                    if st.base_surface is not None:
                        st.screen.blit(st.base_surface, st.img_offset)

                        # Committed strokes (cached surface, re-rendered only when dirty)
                        sw, sh = st.screen.get_size()
                        stroke_surf = st.strokes.render(sw, sh, st.scale_factor, st.img_offset)
                        st.screen.blit(stroke_surf, (0, 0))

                        # Live in-progress stroke (drawn directly, no caching)
                        if st.drawing and len(st.current_stroke_points) >= 2:
                            st.strokes.render_live(
                                st.screen,
                                st.current_stroke_points,
                                st.my_color,
                                st.brush_width,
                                st.scale_factor,
                                st.img_offset,
                            )

                    # --- UI ---
                    sw, sh = st.screen.get_size()
                    icon_y = sh - ICON_SIZE - UI_PADDING
                    icon_x = UI_PADDING

                    st.color_icon_rect = glass.draw_color_icon(st.screen, st.my_color, (icon_x, icon_y))
                    if st.color_expanded:
                        st.color_hitboxes, st.color_panel_rect = glass.draw_color_panel(
                            st.screen, st.my_color, (icon_x, icon_y)
                        )
                    else:
                        st.color_hitboxes = []
                        st.color_panel_rect = pygame.Rect(0, 0, 0, 0)

                    icon_x += ICON_SIZE + 8
                    st.thick_icon_rect = glass.draw_thickness_icon(
                        st.screen, st.brush_width, st.my_color, (icon_x, icon_y)
                    )
                    if st.thick_expanded:
                        st.thick_hitboxes, st.thick_panel_rect = glass.draw_thickness_panel(
                            st.screen, st.brush_width, st.my_color, (icon_x, icon_y)
                        )
                    else:
                        st.thick_hitboxes = []
                        st.thick_panel_rect = pygame.Rect(0, 0, 0, 0)

                    if st.hover_name:
                        glass.draw_tooltip(st.screen, st.hover_name, mouse_pos)

                    pygame.display.flip()
                    await asyncio.sleep(0)
                    clock.tick(60)

            finally:
                reader_task.cancel()
                try:
                    await reader_task
                except asyncio.CancelledError:
                    pass
                # Force-close the socket so the context manager doesn't hang
                try:
                    await asyncio.wait_for(ws.close(), timeout=1.0)
                except (asyncio.TimeoutError, Exception):
                    pass

    except (ConnectionRefusedError, OSError) as e:
        print(f"Could not connect to server: {e}")
        sys.exit(1)
    except websockets.ConnectionClosed:
        print("Server closed the connection.")
    finally:
        pygame.quit()
        print("Client shut down.")


def main():
    parser = argparse.ArgumentParser(description="Doodle client")
    parser.add_argument(
        "server",
        nargs="?",
        default="ws://localhost:8765",
        help="WebSocket server URL (default: ws://localhost:8765)",
    )
    args = parser.parse_args()
    asyncio.run(run_client(args.server))


if __name__ == "__main__":
    main()
