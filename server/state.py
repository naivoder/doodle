"""Shared mutable state for all active connections."""

from __future__ import annotations

import os
import random
from typing import Any

from pydantic import BaseModel
from websockets.asyncio.server import ServerConnection

from .images import load_image
from .presidents import PRESIDENTS
from .transitions import TRANSITIONS, CutTransition, Transition, TransitionMessage

COLOR_PALETTE: list[list[int]] = [
    [231, 76, 60],  [46, 134, 193],  [39, 174, 96],
    [243, 156, 18], [142, 68, 173],  [26, 188, 156],
    [241, 196, 15], [52, 73, 94],
]


class ClientInfo(BaseModel):
    """Per-connection client metadata."""
    color: list[int]
    name: str
    id: int


class ServerState:
    """Central state for the slideshow server: images, clients, and draw history."""

    def __init__(self, images: list[str], transition_name: str, slide_interval: int) -> None:
        self.images = images
        self.slide_interval = slide_interval
        self.transition: Transition = TRANSITIONS.get(transition_name, CutTransition)()
        self.current_index: int = 0

        self.image_b64: str = ""
        self.image_width: int = 0
        self.image_height: int = 0

        self.clients: dict[ServerConnection, ClientInfo] = {}
        self.next_color_index: int = 0
        self.next_client_id: int = 1
        self._used_presidents: list[str] = []

        self.draw_history: list[dict[str, Any]] = []

    def _pick_president(self) -> str:
        if not self._used_presidents:
            self._used_presidents = list(PRESIDENTS)
            random.shuffle(self._used_presidents)
        return self._used_presidents.pop()

    def load_current_image(self) -> None:
        path = self.images[self.current_index]
        self.image_b64, self.image_width, self.image_height = load_image(path)
        print(f"  Image loaded: {os.path.basename(path)} ({self.image_width}x{self.image_height})")

    def advance_image(self) -> list[TransitionMessage]:
        """Move to the next slide and return transition messages to broadcast."""
        old_b64 = self.image_b64
        self.current_index = (self.current_index + 1) % len(self.images)
        self.load_current_image()
        self.draw_history.clear()
        return self.transition.start(old_b64, self.image_b64, self.image_width, self.image_height)

    def assign_client(self, ws: ServerConnection) -> ClientInfo:
        """Register a new connection and return its assigned ClientInfo."""
        color = COLOR_PALETTE[self.next_color_index % len(COLOR_PALETTE)]
        self.next_color_index += 1
        cid = self.next_client_id
        self.next_client_id += 1
        info = ClientInfo(color=color, name=self._pick_president(), id=cid)
        self.clients[ws] = info
        return info

    def remove_client(self, ws: ServerConnection) -> None:
        self.clients.pop(ws, None)

    def add_stroke(self, stroke: dict[str, Any]) -> None:
        self.draw_history.append(stroke)

    def build_user_list(self) -> list[dict[str, Any]]:
        return [c.model_dump() for c in self.clients.values()]
