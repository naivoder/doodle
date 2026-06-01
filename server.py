#!/usr/bin/env python3
"""WebSocket server that shares an image with all connected clients."""

import argparse
import asyncio
import base64
import io
import json
import signal

import websockets

# Global state
connected_clients = set()
image_payload = None


def load_image(path):
    """Read an image file and return a base64-encoded PNG string."""
    # Use PIL if available for format normalization, otherwise send raw bytes
    try:
        from PIL import Image

        img = Image.open(path)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        width, height = img.size
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    except ImportError:
        # Fallback: read raw file bytes (must already be PNG)
        with open(path, "rb") as f:
            raw = f.read()
        b64 = base64.b64encode(raw).decode("ascii")
        # Try to parse PNG header for dimensions
        width, height = _png_dimensions(raw)

    return {"type": "image_sync", "data": b64, "width": width, "height": height}


def _png_dimensions(raw):
    """Extract width and height from a PNG file header."""
    import struct

    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        print("Warning: file does not appear to be PNG. Window may not size correctly.")
        return 800, 600
    ihdr = raw[16:24]
    width, height = struct.unpack(">II", ihdr)
    return width, height


async def handler(websocket):
    """Handle a single client connection."""
    connected_clients.add(websocket)
    remote = websocket.remote_address
    print(f"[+] Client connected: {remote[0]}:{remote[1]}  ({len(connected_clients)} total)")

    try:
        # Send the image to the newly connected client
        await websocket.send(json.dumps(image_payload))
        print(f"    Sent image to {remote[0]}:{remote[1]}")

        # Keep connection alive and listen for future messages (e.g. draw events)
        async for message in websocket:
            # For now, just echo/broadcast any message to all other clients
            data = json.loads(message)
            others = connected_clients - {websocket}
            if others:
                await asyncio.gather(*(c.send(message) for c in others))

    except websockets.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"[-] Client disconnected: {remote[0]}:{remote[1]}  ({len(connected_clients)} total)")


async def main(host, port, image_path):
    global image_payload

    print(f"Loading image: {image_path}")
    image_payload = load_image(image_path)
    print(f"Image loaded: {image_payload['width']}x{image_payload['height']}")

    # Graceful shutdown on Ctrl+C
    stop = asyncio.get_event_loop().create_future()

    def _signal_handler():
        if not stop.done():
            stop.set_result(None)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    async with websockets.serve(handler, host, port):
        print(f"Server listening on ws://{host}:{port}")
        print("Press Ctrl+C to stop.\n")
        await stop

    print("\nServer shut down.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Doodle image server")
    parser.add_argument("image", help="Path to the image file to share")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    args = parser.parse_args()

    asyncio.run(main(args.host, args.port, args.image))
