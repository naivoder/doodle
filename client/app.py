"""Main client loop: events, messages, rendering. The beating heart of the doodle client."""

from __future__ import annotations

import asyncio
import base64
import collections
import json
import sys
from typing import Any

import pygame
import websockets

from .constants import ICON_SIZE, TARGET_HEIGHT, TARGET_WIDTH, UI_PADDING
from .network import ws_reader
from .state import ClientState
from .ui import GlassUI


def _process_events(st: ClientState, send_queue: collections.deque[dict[str, Any]]) -> tuple[int, int]:
    """Drain the pygame event queue. Returns current mouse position."""
    mouse_pos = pygame.mouse.get_pos()

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
                stroke: dict[str, Any] = {
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

    return mouse_pos


def _update_hover(st: ClientState, mouse_pos: tuple[int, int]) -> None:
    """Update panel expansion and stroke hover tooltip state."""
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


def _process_messages(st: ClientState, msg_queue: collections.deque[dict[str, Any]]) -> None:
    """Apply all queued server messages to client state."""
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


def _render(st: ClientState, glass: GlassUI, mouse_pos: tuple[int, int]) -> None:
    """Composite the image, strokes, and UI onto the screen."""
    st.screen.fill((20, 20, 25))

    if st.base_surface is not None:
        st.screen.blit(st.base_surface, st.img_offset)

        sw, sh = st.screen.get_size()
        stroke_surf = st.strokes.render(sw, sh, st.scale_factor, st.img_offset)
        st.screen.blit(stroke_surf, (0, 0))

        if st.drawing and len(st.current_stroke_points) >= 2:
            st.strokes.render_live(
                st.screen, st.current_stroke_points, st.my_color,
                st.brush_width, st.scale_factor, st.img_offset,
            )

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

    glass.draw_user_count(st.screen, len(st.users))

    if st.hover_name:
        glass.draw_tooltip(st.screen, st.hover_name, mouse_pos)

    pygame.display.flip()


async def run_client(server_url: str, username: str | None = None) -> None:
    """Connect to the server and run the pygame event/render loop."""
    pygame.init()

    st = ClientState()
    st.screen = pygame.display.set_mode(
        (TARGET_WIDTH, TARGET_HEIGHT), pygame.RESIZABLE | pygame.SCALED
    )
    pygame.display.set_caption("Doodle - Shared Canvas")

    glass = GlassUI()
    glass.init_fonts()
    clock = pygame.time.Clock()
    msg_queue: collections.deque[dict[str, Any]] = collections.deque()
    send_queue: collections.deque[dict[str, Any]] = collections.deque()

    if username:
        send_queue.append({"type": "name_change", "name": username})

    print(f"Connecting to {server_url} ...")

    try:
        async with websockets.connect(server_url, max_size=20 * 1024 * 1024, close_timeout=2) as ws:
            print("Connected. Waiting for image...")
            reader_task = asyncio.create_task(ws_reader(ws, msg_queue, st))

            try:
                while st.running:
                    mouse_pos = _process_events(st, send_queue)
                    _update_hover(st, mouse_pos)
                    _process_messages(st, msg_queue)

                    while send_queue:
                        try:
                            await ws.send(json.dumps(send_queue.popleft()))
                        except websockets.ConnectionClosed:
                            st.running = False
                            break

                    _render(st, glass, mouse_pos)
                    await asyncio.sleep(0)
                    clock.tick(60)

            finally:
                reader_task.cancel()
                try:
                    await reader_task
                except asyncio.CancelledError:
                    pass
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
