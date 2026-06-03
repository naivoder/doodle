#!/usr/bin/env python3
"""WebSocket server for collaborative doodle slideshow."""

import argparse
import asyncio
import base64
import io
import json
import os
import signal
import time

import websockets

# ---------------------------------------------------------------------------
# Transitions — extensible registry
# ---------------------------------------------------------------------------

TRANSITIONS = {}


def register_transition(name):
    """Decorator to register a transition strategy by name."""
    def decorator(cls):
        TRANSITIONS[name] = cls
        return cls
    return decorator


class Transition:
    """Base class for image transitions."""

    def __init__(self, duration=1.0):
        self.duration = duration

    def start(self, old_image_b64, new_image_b64, width, height):
        """Return a list of messages to send to clients for this transition."""
        raise NotImplementedError


@register_transition("cut")
class CutTransition(Transition):
    """Immediate hard cut — no animation."""

    def __init__(self):
        super().__init__(duration=0)

    def start(self, old_image_b64, new_image_b64, width, height):
        return [{"type": "image_sync", "data": new_image_b64, "width": width, "height": height}]


@register_transition("crossfade")
class CrossfadeTransition(Transition):
    """Client-side crossfade between two images."""

    def __init__(self, duration=2.0):
        super().__init__(duration=duration)

    def start(self, old_image_b64, new_image_b64, width, height):
        return [{
            "type": "transition",
            "transition": "crossfade",
            "duration": self.duration,
            "from_data": old_image_b64,
            "to_data": new_image_b64,
            "width": width,
            "height": height,
        }]


# ---------------------------------------------------------------------------
# Image loading
# ---------------------------------------------------------------------------

def load_image(path):
    """Read an image file and return (b64_string, width, height)."""
    try:
        from PIL import Image
        img = Image.open(path).convert("RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return b64, img.size[0], img.size[1]
    except ImportError:
        with open(path, "rb") as f:
            raw = f.read()
        b64 = base64.b64encode(raw).decode("ascii")
        w, h = _png_dimensions(raw)
        return b64, w, h


def _png_dimensions(raw):
    import struct
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return 800, 600
    return struct.unpack(">II", raw[16:24])


def discover_images(path):
    """Return a sorted list of image file paths from a file or directory."""
    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"}
    if os.path.isfile(path):
        return [path]
    entries = sorted(os.listdir(path))
    return [os.path.join(path, e) for e in entries if os.path.splitext(e)[1].lower() in IMAGE_EXTS]


# ---------------------------------------------------------------------------
# Server state
# ---------------------------------------------------------------------------

class ServerState:
    """Central mutable state for the running server."""

    # Visually distinct default colors assigned round-robin
    COLOR_PALETTE = [
        [231, 76, 60],    # red
        [46, 134, 193],   # blue
        [39, 174, 96],    # green
        [243, 156, 18],   # orange
        [142, 68, 173],   # purple
        [26, 188, 156],   # teal
        [241, 196, 15],   # yellow
        [52, 73, 94],     # dark slate
    ]

    CONSOLIDATION_DELAY = 3.0  # seconds before strokes get consolidated

    def __init__(self, images, transition_name, slide_interval):
        self.images = images
        self.slide_interval = slide_interval
        self.transition = TRANSITIONS.get(transition_name, CutTransition)()
        self.current_index = 0

        # Current image data
        self.image_b64 = None
        self.image_width = 0
        self.image_height = 0

        # Client tracking: ws -> {color, name}
        self.clients = {}
        self.next_color_index = 0
        self.next_client_id = 1

        # Drawing state
        self.draw_history = []        # unconsolidated recent strokes
        self.consolidated_b64 = None  # base64 PNG of flattened old strokes
        self.last_stroke_time = 0.0

    def load_current_image(self):
        path = self.images[self.current_index]
        self.image_b64, self.image_width, self.image_height = load_image(path)
        print(f"  Image loaded: {os.path.basename(path)} ({self.image_width}x{self.image_height})")

    def advance_image(self):
        """Move to the next image in the slideshow."""
        old_b64 = self.image_b64
        self.current_index = (self.current_index + 1) % len(self.images)
        self.load_current_image()
        self.draw_history.clear()
        self.consolidated_b64 = None
        return self.transition.start(old_b64, self.image_b64, self.image_width, self.image_height)

    def assign_client(self, ws):
        color = self.COLOR_PALETTE[self.next_color_index % len(self.COLOR_PALETTE)]
        self.next_color_index += 1
        cid = self.next_client_id
        self.next_client_id += 1
        name = f"User {cid}"
        self.clients[ws] = {"color": color, "name": name, "id": cid}
        return color, name, cid

    def remove_client(self, ws):
        if ws in self.clients:
            del self.clients[ws]

    def add_stroke(self, stroke):
        self.draw_history.append(stroke)
        self.last_stroke_time = time.monotonic()

    def build_user_list(self):
        return [{"id": c["id"], "name": c["name"], "color": c["color"]} for c in self.clients.values()]

    def consolidation_snapshot(self):
        """Return strokes eligible for consolidation, then clear them."""
        if not self.draw_history:
            return None
        elapsed = time.monotonic() - self.last_stroke_time
        if elapsed < self.CONSOLIDATION_DELAY:
            return None
        snapshot = list(self.draw_history)
        self.draw_history.clear()
        return snapshot


# ---------------------------------------------------------------------------
# Broadcasting helpers
# ---------------------------------------------------------------------------

async def broadcast(state, message_str, exclude=None):
    targets = set(state.clients) - ({exclude} if exclude else set())
    if targets:
        await asyncio.gather(*(c.send(message_str) for c in targets), return_exceptions=True)


async def broadcast_user_list(state):
    msg = json.dumps({"type": "user_list", "users": state.build_user_list()})
    await broadcast(state, msg)


# ---------------------------------------------------------------------------
# Connection handler
# ---------------------------------------------------------------------------

async def handler(websocket, state):
    color, name, cid = state.assign_client(websocket)
    remote = websocket.remote_address
    print(f"[+] {name} connected from {remote[0]}:{remote[1]}  color={color}  ({len(state.clients)} total)")

    try:
        # Send current image
        await websocket.send(json.dumps({
            "type": "image_sync",
            "data": state.image_b64,
            "width": state.image_width,
            "height": state.image_height,
        }))

        # Send assigned color + identity
        await websocket.send(json.dumps({
            "type": "color_assign",
            "color": color,
            "name": name,
            "id": cid,
        }))

        # Send consolidated layer if any
        if state.consolidated_b64:
            await websocket.send(json.dumps({
                "type": "consolidated_layer",
                "data": state.consolidated_b64,
            }))

        # Send unconsolidated strokes
        if state.draw_history:
            await websocket.send(json.dumps({
                "type": "draw_history",
                "strokes": state.draw_history,
            }))

        # Broadcast updated user list
        await broadcast_user_list(state)

        # Listen for messages
        async for message in websocket:
            data = json.loads(message)

            if data["type"] == "draw":
                state.add_stroke(data)
                await broadcast(state, message, exclude=websocket)

            elif data["type"] == "color_change":
                new_color = data["color"]
                state.clients[websocket]["color"] = new_color
                await websocket.send(json.dumps({"type": "color_assign", "color": new_color, "name": name, "id": cid}))
                await broadcast_user_list(state)

            elif data["type"] == "name_change":
                new_name = data["name"][:20]
                state.clients[websocket]["name"] = new_name
                await broadcast_user_list(state)

    except websockets.ConnectionClosed:
        pass
    finally:
        state.remove_client(websocket)
        print(f"[-] {name} disconnected  ({len(state.clients)} total)")
        if state.clients:
            await broadcast_user_list(state)


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

async def slideshow_loop(state):
    """Advance to the next image on a timer."""
    if len(state.images) < 2:
        return  # single image, no slideshow
    while True:
        await asyncio.sleep(state.slide_interval)
        print(f"\n--- Advancing slideshow (image {state.current_index + 1}/{len(state.images)}) ---")
        messages = state.advance_image()

        # Notify all clients: clear doodles + new image
        await broadcast(state, json.dumps({"type": "clear_doodles"}))
        for msg in messages:
            await broadcast(state, json.dumps(msg))


async def consolidation_loop(state):
    """Periodically consolidate old strokes into a single layer."""
    while True:
        await asyncio.sleep(1.0)
        snapshot = state.consolidation_snapshot()
        if snapshot is None:
            continue

        try:
            from PIL import Image, ImageDraw
            w, h = state.image_width, state.image_height
            layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(layer)

            # Render existing consolidated layer first
            if state.consolidated_b64:
                existing = Image.open(io.BytesIO(base64.b64decode(state.consolidated_b64)))
                layer.paste(existing, (0, 0), existing)

            # Render new strokes
            for stroke in snapshot:
                color = tuple(stroke["color"])
                points = stroke["points"]
                width = stroke.get("width", 4)
                rgba = color + (255,) if len(color) == 3 else color
                if len(points) == 1:
                    x, y = points[0]
                    r = width // 2
                    draw.ellipse([x - r, y - r, x + r, y + r], fill=rgba)
                else:
                    for i in range(len(points) - 1):
                        draw.line([tuple(points[i]), tuple(points[i + 1])], fill=rgba, width=width)

            buf = io.BytesIO()
            layer.save(buf, format="PNG")
            state.consolidated_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

            # Tell clients about the consolidated layer
            await broadcast(state, json.dumps({
                "type": "consolidated_layer",
                "data": state.consolidated_b64,
            }))

        except ImportError:
            # Without PIL, just keep strokes in history (no consolidation)
            state.draw_history = snapshot + state.draw_history


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(host, port, image_path, transition_name, slide_interval):
    images = discover_images(image_path)
    if not images:
        print(f"Error: no images found at '{image_path}'")
        return

    print(f"Found {len(images)} image(s) in slideshow")
    state = ServerState(images, transition_name, slide_interval)
    state.load_current_image()

    stop = asyncio.get_event_loop().create_future()

    def _signal_handler():
        if not stop.done():
            stop.set_result(None)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    async with websockets.serve(lambda ws: handler(ws, state), host, port):
        print(f"Server listening on ws://{host}:{port}")
        if len(images) > 1:
            print(f"Slideshow: {slide_interval}s per image, transition: {transition_name}")
        print("Press Ctrl+C to stop.\n")

        slide_task = asyncio.create_task(slideshow_loop(state))
        consolidation_task = asyncio.create_task(consolidation_loop(state))

        try:
            await stop
        finally:
            slide_task.cancel()
            consolidation_task.cancel()
            for t in (slide_task, consolidation_task):
                try:
                    await t
                except asyncio.CancelledError:
                    pass

    print("\nServer shut down.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Doodle slideshow server")
    parser.add_argument(
        "image",
        nargs="?",
        default="sample.png",
        help="Path to an image file or directory of images (default: sample.png)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    parser.add_argument(
        "--transition",
        default="cut",
        choices=sorted(TRANSITIONS.keys()),
        help="Transition effect between slides (default: cut)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds between slide changes (default: 60 = 1 minute)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port, args.image, args.transition, args.interval))
