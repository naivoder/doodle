"""WebSocket connection handling and slideshow background task."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection

from .state import ServerState


async def broadcast(state: ServerState, message_str: str, exclude: ServerConnection | None = None) -> None:
    """Send a pre-serialized JSON string to all connected clients."""
    targets = set(state.clients) - ({exclude} if exclude else set())
    if targets:
        await asyncio.gather(*(c.send(message_str) for c in targets), return_exceptions=True)


async def broadcast_user_list(state: ServerState) -> None:
    msg = json.dumps({"type": "user_list", "users": state.build_user_list()})
    await broadcast(state, msg)


async def handle_connection(websocket: ServerConnection, state: ServerState) -> None:
    """Lifecycle handler for a single client connection."""
    info = state.assign_client(websocket)
    remote = websocket.remote_address
    print(f"[+] {info.name} connected from {remote[0]}:{remote[1]}  color={info.color}  ({len(state.clients)} total)")

    try:
        await websocket.send(json.dumps({
            "type": "image_sync",
            "data": state.image_b64,
            "width": state.image_width,
            "height": state.image_height,
        }))

        await websocket.send(json.dumps({
            "type": "color_assign",
            "color": info.color,
            "name": info.name,
            "id": info.id,
        }))

        if state.draw_history:
            await websocket.send(json.dumps({
                "type": "draw_history",
                "strokes": state.draw_history,
            }))

        await broadcast_user_list(state)

        async for message in websocket:
            data: dict[str, Any] = json.loads(message)

            if data["type"] == "draw":
                data["name"] = state.clients[websocket].name
                enriched = json.dumps(data)
                state.add_stroke(data)
                await broadcast(state, enriched, exclude=websocket)

            elif data["type"] == "color_change":
                state.clients[websocket].color = data["color"]
                await websocket.send(json.dumps({
                    "type": "color_assign",
                    "color": data["color"],
                    "name": state.clients[websocket].name,
                    "id": info.id,
                }))
                await broadcast_user_list(state)

            elif data["type"] == "name_change":
                state.clients[websocket].name = data["name"][:20]
                await broadcast_user_list(state)

    except websockets.ConnectionClosed:
        pass
    finally:
        state.remove_client(websocket)
        print(f"[-] {info.name} disconnected  ({len(state.clients)} total)")
        if state.clients:
            await broadcast_user_list(state)


async def slideshow_loop(state: ServerState) -> None:
    """Advance slides on a timer. Exits immediately if there's only one image."""
    if len(state.images) < 2:
        return
    while True:
        await asyncio.sleep(state.slide_interval)
        print(f"\n--- Advancing slideshow (image {state.current_index + 1}/{len(state.images)}) ---")
        messages = state.advance_image()
        await broadcast(state, json.dumps({"type": "clear_doodles"}))
        for msg in messages:
            await broadcast(state, json.dumps(msg))
