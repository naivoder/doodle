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
UI_PADDING = 12
UI_CORNER_RADIUS = 16
LEGEND_WIDTH = 180
COLOR_SWATCH_SIZE = 20
COLOR_PICKER_COLUMNS = 6

# Glassmorphism palette
GLASS_BG = (255, 255, 255, 40)
GLASS_BORDER = (255, 255, 255, 80)
GLASS_TEXT = (255, 255, 255)
GLASS_HIGHLIGHT = (255, 255, 255, 60)

# Color picker palette
PICKER_COLORS = [
    [231, 76, 60],    [192, 57, 43],    [211, 84, 0],
    [243, 156, 18],   [241, 196, 15],   [39, 174, 96],
    [46, 134, 193],   [41, 128, 185],   [142, 68, 173],
    [26, 188, 156],   [22, 160, 133],   [52, 73, 94],
    [236, 240, 241],  [189, 195, 199],  [127, 140, 141],
    [44, 62, 80],     [255, 255, 255],  [30, 30, 30],
]


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def draw_stroke(surface, stroke):
    color = tuple(stroke["color"])
    points = stroke["points"]
    width = stroke.get("width", 4)
    if len(points) == 1:
        pygame.draw.circle(surface, color, points[0], max(width // 2, 1))
    elif len(points) >= 2:
        pygame.draw.lines(surface, color, False, points, width)


def scale_to_fit(img_w, img_h, target_w, target_h):
    ratio = min(target_w / img_w, target_h / img_h)
    return int(img_w * ratio), int(img_h * ratio)


# ---------------------------------------------------------------------------
# Glassmorphism UI renderer
# ---------------------------------------------------------------------------

class GlassUI:

    def __init__(self):
        self.font = None
        self.small_font = None

    def init_fonts(self):
        self.font = pygame.font.SysFont("Helvetica,Arial,sans-serif", UI_FONT_SIZE)
        self.small_font = pygame.font.SysFont("Helvetica,Arial,sans-serif", UI_FONT_SIZE - 2)

    def draw_glass_panel(self, target, rect):
        panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(panel, GLASS_BG, panel.get_rect(), border_radius=UI_CORNER_RADIUS)
        pygame.draw.rect(panel, GLASS_BORDER, panel.get_rect(), width=1, border_radius=UI_CORNER_RADIUS)
        highlight_rect = pygame.Rect(4, 2, rect.width - 8, 1)
        pygame.draw.rect(panel, GLASS_HIGHLIGHT, highlight_rect, border_radius=1)
        target.blit(panel, rect.topleft)

    def draw_text(self, target, text, pos, color=GLASS_TEXT, font=None):
        f = font or self.font
        shadow = f.render(text, True, (0, 0, 0))
        shadow.set_alpha(80)
        target.blit(shadow, (pos[0] + 1, pos[1] + 1))
        target.blit(f.render(text, True, color), pos)

    def draw_legend(self, target, users, screen_w, screen_h):
        if not users:
            return pygame.Rect(0, 0, 0, 0)

        row_height = UI_FONT_SIZE + 8
        header_height = row_height + 4
        panel_h = header_height + len(users) * row_height + UI_PADDING
        panel_w = LEGEND_WIDTH
        panel_x = screen_w - panel_w - UI_PADDING
        panel_y = UI_PADDING

        rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        self.draw_glass_panel(target, rect)
        self.draw_text(target, "Connected Users", (panel_x + UI_PADDING, panel_y + 8))

        y = panel_y + header_height
        for user in users:
            color = tuple(user["color"])
            cx = panel_x + UI_PADDING + 6
            cy = y + row_height // 2
            pygame.draw.circle(target, color, (cx, cy), 5)
            pygame.draw.circle(target, (255, 255, 255, 120), (cx, cy), 5, 1)
            self.draw_text(target, user["name"], (cx + 14, y + 2), font=self.small_font)
            y += row_height

        return rect

    def draw_color_picker(self, target, current_color, screen_w, screen_h):
        cols = COLOR_PICKER_COLUMNS
        rows = math.ceil(len(PICKER_COLORS) / cols)
        swatch = COLOR_SWATCH_SIZE
        gap = 4
        inner_w = cols * (swatch + gap) - gap
        inner_h = rows * (swatch + gap) - gap
        header_h = UI_FONT_SIZE + 12
        panel_w = inner_w + UI_PADDING * 2
        panel_h = header_h + inner_h + UI_PADDING * 2

        panel_x = UI_PADDING
        panel_y = screen_h - panel_h - UI_PADDING

        rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        self.draw_glass_panel(target, rect)
        self.draw_text(target, "Brush Color", (panel_x + UI_PADDING, panel_y + 8))

        hitboxes = []
        bx = panel_x + UI_PADDING
        by = panel_y + header_h + UI_PADDING // 2
        for i, color in enumerate(PICKER_COLORS):
            col = i % cols
            row = i // cols
            x = bx + col * (swatch + gap)
            y = by + row * (swatch + gap)
            sr = pygame.Rect(x, y, swatch, swatch)
            pygame.draw.rect(target, tuple(color), sr, border_radius=4)
            if color == list(current_color):
                pygame.draw.rect(target, (255, 255, 255), sr.inflate(4, 4), width=2, border_radius=6)
            hitboxes.append((sr, color))

        return hitboxes, rect


# ---------------------------------------------------------------------------
# Client state
# ---------------------------------------------------------------------------

class ClientState:
    """All mutable state for the running client, kept in one place."""

    def __init__(self):
        self.screen = None
        self.base_surface = None
        self.consolidated_surface = None
        self.draw_surface = None
        self.scale_factor = 1.0
        self.img_offset = (0, 0)
        self.native_w = 0
        self.native_h = 0
        # Cached scaled overlays — rebuilt only when source changes
        self._scaled_cons = None
        self._scaled_draw = None
        self._cons_dirty = True
        self._draw_dirty = True

        self.my_color = [255, 255, 255]
        self.my_name = ""
        self.my_id = 0
        self.brush_width = 4
        self.drawing = False
        self.current_stroke_points = []
        self.users = []
        self.color_hitboxes = []
        self.legend_rect = pygame.Rect(0, 0, 0, 0)
        self.picker_rect = pygame.Rect(0, 0, 0, 0)
        self.running = True

    def mark_draw_dirty(self):
        self._draw_dirty = True

    def mark_cons_dirty(self):
        self._cons_dirty = True

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

    def rebuild_surfaces(self, w, h, png_bytes):
        raw = pygame.image.load(io.BytesIO(png_bytes))
        self.native_w, self.native_h = w, h
        self._compute_layout()
        sf = self.scale_factor
        if sf == 1.0:
            self.base_surface = raw
        else:
            dw, dh = int(w * sf), int(h * sf)
            self.base_surface = pygame.transform.smoothscale(raw, (dw, dh))
        self.draw_surface = pygame.Surface((w, h), pygame.SRCALPHA)
        self.consolidated_surface = pygame.Surface((w, h), pygame.SRCALPHA)
        self._cons_dirty = True
        self._draw_dirty = True

    def handle_resize(self, new_w, new_h):
        self.screen = pygame.display.set_mode((new_w, new_h), pygame.RESIZABLE)
        if self.native_w > 0:
            self._compute_layout()
            self._cons_dirty = True
            self._draw_dirty = True

    def screen_to_canvas(self, pos):
        return (
            int((pos[0] - self.img_offset[0]) / self.scale_factor),
            int((pos[1] - self.img_offset[1]) / self.scale_factor),
        )

    def is_on_canvas(self, pos):
        if self.legend_rect.collidepoint(pos) or self.picker_rect.collidepoint(pos):
            return False
        x, y = pos
        ox, oy = self.img_offset
        sf = self.scale_factor
        return ox <= x < ox + self.native_w * sf and oy <= y < oy + self.native_h * sf

    def get_scaled_overlay(self, which):
        """Return a cached scaled version of draw or consolidated surface."""
        dw = int(self.native_w * self.scale_factor)
        dh = int(self.native_h * self.scale_factor)
        if dw <= 0 or dh <= 0:
            return None
        if which == "draw":
            if self._draw_dirty:
                if self.scale_factor == 1.0:
                    self._scaled_draw = self.draw_surface
                else:
                    self._scaled_draw = pygame.transform.scale(self.draw_surface, (dw, dh))
                self._draw_dirty = False
            return self._scaled_draw
        else:
            if self._cons_dirty:
                if self.scale_factor == 1.0:
                    self._scaled_cons = self.consolidated_surface
                else:
                    self._scaled_cons = pygame.transform.scale(self.consolidated_surface, (dw, dh))
                self._cons_dirty = False
            return self._scaled_cons


# ---------------------------------------------------------------------------
# WebSocket reader task
# ---------------------------------------------------------------------------

async def ws_reader(ws, msg_queue, state):
    """Read websocket messages into a queue. Exits on close or error."""
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
    st.screen = pygame.display.set_mode((TARGET_WIDTH, TARGET_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("Doodle - Shared Canvas")

    glass = GlassUI()
    glass.init_fonts()
    clock = pygame.time.Clock()
    msg_queue = collections.deque()
    send_queue = collections.deque()

    print(f"Connecting to {server_url} ...")

    try:
        async with websockets.connect(server_url) as ws:
            print("Connected. Waiting for image...")

            reader_task = asyncio.create_task(ws_reader(ws, msg_queue, st))

            try:
                while st.running:
                    # --- Pygame events ---
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            st.running = False

                        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                            st.running = False

                        elif event.type == pygame.VIDEORESIZE:
                            st.handle_resize(event.w, event.h)

                        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            clicked_color = False
                            for sr, color in st.color_hitboxes:
                                if sr.collidepoint(event.pos):
                                    st.my_color = list(color)
                                    send_queue.append({"type": "color_change", "color": st.my_color})
                                    clicked_color = True
                                    break
                            if not clicked_color and st.draw_surface is not None and st.is_on_canvas(event.pos):
                                st.drawing = True
                                st.current_stroke_points = [st.screen_to_canvas(event.pos)]

                        elif event.type == pygame.MOUSEMOTION and st.drawing:
                            cp = st.screen_to_canvas(event.pos)
                            st.current_stroke_points.append(cp)
                            if len(st.current_stroke_points) >= 2:
                                pygame.draw.line(
                                    st.draw_surface,
                                    tuple(st.my_color),
                                    st.current_stroke_points[-2],
                                    st.current_stroke_points[-1],
                                    st.brush_width,
                                )
                                st.mark_draw_dirty()

                        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                            if st.drawing and st.current_stroke_points:
                                send_queue.append({
                                    "type": "draw",
                                    "color": st.my_color,
                                    "points": st.current_stroke_points,
                                    "width": st.brush_width,
                                })
                            st.drawing = False
                            st.current_stroke_points = []

                    # --- Process all pending WS messages ---
                    while msg_queue:
                        msg = msg_queue.popleft()
                        mtype = msg["type"]

                        if mtype == "image_sync":
                            png_bytes = base64.b64decode(msg["data"])
                            st.rebuild_surfaces(msg["width"], msg["height"], png_bytes)
                            print(f"Image loaded: {msg['width']}x{msg['height']}")

                        elif mtype == "transition":
                            png_bytes = base64.b64decode(msg["to_data"])
                            st.rebuild_surfaces(msg["width"], msg["height"], png_bytes)

                        elif mtype == "color_assign":
                            st.my_color = msg["color"]
                            st.my_name = msg.get("name", "")
                            st.my_id = msg.get("id", 0)

                        elif mtype == "user_list":
                            st.users = msg["users"]

                        elif mtype == "draw_history":
                            if st.draw_surface is not None:
                                for stroke in msg["strokes"]:
                                    draw_stroke(st.draw_surface, stroke)
                                st.mark_draw_dirty()

                        elif mtype == "draw":
                            if st.draw_surface is not None:
                                draw_stroke(st.draw_surface, msg)
                                st.mark_draw_dirty()

                        elif mtype == "consolidated_layer":
                            if st.consolidated_surface is not None:
                                png_bytes = base64.b64decode(msg["data"])
                                st.consolidated_surface = pygame.image.load(io.BytesIO(png_bytes)).convert_alpha()
                                st.mark_cons_dirty()
                                if st.draw_surface is not None:
                                    st.draw_surface.fill((0, 0, 0, 0))
                                    st.mark_draw_dirty()

                        elif mtype == "clear_doodles":
                            if st.draw_surface is not None:
                                st.draw_surface.fill((0, 0, 0, 0))
                                st.mark_draw_dirty()
                            if st.consolidated_surface is not None:
                                st.consolidated_surface.fill((0, 0, 0, 0))
                                st.mark_cons_dirty()

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

                        cons = st.get_scaled_overlay("cons")
                        if cons is not None:
                            st.screen.blit(cons, st.img_offset)

                        draw = st.get_scaled_overlay("draw")
                        if draw is not None:
                            st.screen.blit(draw, st.img_offset)

                    sw, sh = st.screen.get_size()
                    st.legend_rect = glass.draw_legend(st.screen, st.users, sw, sh)
                    st.color_hitboxes, st.picker_rect = glass.draw_color_picker(st.screen, st.my_color, sw, sh)

                    pygame.display.flip()

                    # Yield to the event loop briefly so the WS reader task can run
                    await asyncio.sleep(0)
                    clock.tick(60)

            finally:
                reader_task.cancel()
                try:
                    await reader_task
                except asyncio.CancelledError:
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
