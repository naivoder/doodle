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


async def run_client(server_url):
    pygame.init()

    # Placeholder surface until we receive the image
    screen = None
    surface = None
    running = True
    clock = pygame.time.Clock()

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

                # --- Check for WebSocket messages (non-blocking) ---
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.01)
                    msg = json.loads(raw)

                    if msg["type"] == "image_sync":
                        print(f"Received image: {msg['width']}x{msg['height']}")
                        png_bytes = base64.b64decode(msg["data"])
                        surface = pygame.image.load(io.BytesIO(png_bytes))

                        # Create / resize window to match image
                        screen = pygame.display.set_mode(
                            (msg["width"], msg["height"]),
                            pygame.RESIZABLE,
                        )
                        pygame.display.set_caption("Doodle - Shared Canvas")

                except asyncio.TimeoutError:
                    pass  # No message available right now

                # --- Render ---
                if screen is not None and surface is not None:
                    screen.blit(surface, (0, 0))
                    pygame.display.flip()

                clock.tick(60)  # Cap at 60 FPS

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
