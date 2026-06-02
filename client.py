#!/usr/bin/env python3
"""Pygame client that connects to the doodle server and displays the shared image."""

import argparse
import asyncio
import base64
import io
import json
import sys

import pygame
import websockets


def draw_stroke(target_surface, stroke):
    """Render a single stroke (list of points) onto a surface."""
    color = tuple(stroke["color"])
    points = stroke["points"]
    width = stroke.get("width", 4)
    if len(points) == 1:
        pygame.draw.circle(target_surface, color, points[0], width // 2)
    else:
        pygame.draw.lines(target_surface, color, False, points, width)


async def run_client(server_url):
    pygame.init()

    screen = None
    base_surface = None  # The original image
    draw_surface = None  # Transparent overlay for all strokes
    running = True
    clock = pygame.time.Clock()

    my_color = [255, 255, 255]
    brush_width = 4
    drawing = False
    current_stroke_points = []

    print(f"Connecting to {server_url} ...")

    try:
        async with websockets.connect(server_url) as ws:
            print("Connected. Waiting for image...")

            while running:
                # --- Handle pygame events ---
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False

                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        running = False

                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if draw_surface is not None:
                            drawing = True
                            current_stroke_points = [list(event.pos)]

                    elif event.type == pygame.MOUSEMOTION and drawing:
                        current_stroke_points.append(list(event.pos))
                        # Draw live preview on the overlay
                        if len(current_stroke_points) >= 2:
                            pygame.draw.line(
                                draw_surface,
                                tuple(my_color),
                                current_stroke_points[-2],
                                current_stroke_points[-1],
                                brush_width,
                            )

                    elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                        if drawing and current_stroke_points:
                            stroke = {
                                "type": "draw",
                                "color": my_color,
                                "points": current_stroke_points,
                                "width": brush_width,
                            }
                            await ws.send(json.dumps(stroke))
                        drawing = False
                        current_stroke_points = []

                # --- Check for WebSocket messages (non-blocking) ---
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.005)
                    msg = json.loads(raw)

                    if msg["type"] == "image_sync":
                        print(f"Received image: {msg['width']}x{msg['height']}")
                        png_bytes = base64.b64decode(msg["data"])
                        base_surface = pygame.image.load(io.BytesIO(png_bytes))
                        w, h = msg["width"], msg["height"]

                        screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
                        pygame.display.set_caption("Doodle - Shared Canvas")

                        draw_surface = pygame.Surface((w, h), pygame.SRCALPHA)
                        draw_surface.fill((0, 0, 0, 0))

                    elif msg["type"] == "color_assign":
                        my_color = msg["color"]
                        print(f"Assigned brush color: {my_color}")

                    elif msg["type"] == "draw_history":
                        for stroke in msg["strokes"]:
                            draw_stroke(draw_surface, stroke)
                        print(f"Replayed {len(msg['strokes'])} strokes from history")

                    elif msg["type"] == "draw":
                        draw_stroke(draw_surface, msg)

                except asyncio.TimeoutError:
                    pass

                # --- Render ---
                if screen is not None and base_surface is not None:
                    screen.blit(base_surface, (0, 0))
                    screen.blit(draw_surface, (0, 0))
                    pygame.display.flip()

                clock.tick(60)

    except (ConnectionRefusedError, OSError) as e:
        print(f"Could not connect to server: {e}")
        print(f"Make sure the server is running at {server_url}")
        sys.exit(1)
    except websockets.ConnectionClosed:
        print("Server closed the connection.")
    finally:
        pygame.quit()
        print("Client shut down.")


def main():
    parser = argparse.ArgumentParser(description="Doodle image client")
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
