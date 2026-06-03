"""WebSocket reader task — receives messages and feeds them into a queue."""

from __future__ import annotations

import collections
import json

import websockets
from websockets.asyncio.client import ClientConnection

from .state import ClientState


async def ws_reader(ws: ClientConnection, msg_queue: collections.deque[dict], state: ClientState) -> None:
    """Read messages until the connection closes, then signal shutdown."""
    try:
        async for raw in ws:
            msg_queue.append(json.loads(raw))
    except websockets.ConnectionClosed:
        pass
    finally:
        state.running = False
