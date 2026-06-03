"""Tests for client message processing — the server-to-client protocol contract."""

import base64
from collections import deque

import pygame
import pytest

from tests.conftest import make_png_bytes
from client.app import _process_messages, _update_hover
from client.state import ClientState


@pytest.fixture
def client_state():
    st = ClientState()
    st.screen = pygame.Surface((800, 600))
    return st


class TestProcessMessages:
    def _queue(self, *msgs):
        return deque(msgs)

    def test_image_sync(self, client_state):
        png = make_png_bytes(50, 50)
        q = self._queue({
            "type": "image_sync",
            "width": 50,
            "height": 50,
            "data": base64.b64encode(png).decode(),
        })
        _process_messages(client_state, q)
        assert client_state.native_w == 50
        assert client_state.native_h == 50
        assert client_state.base_surface is not None

    def test_transition(self, client_state):
        png = make_png_bytes(80, 60)
        q = self._queue({
            "type": "transition",
            "width": 80,
            "height": 60,
            "to_data": base64.b64encode(png).decode(),
        })
        _process_messages(client_state, q)
        assert client_state.native_w == 80
        assert client_state.native_h == 60

    def test_color_assign(self, client_state):
        q = self._queue({
            "type": "color_assign",
            "color": [255, 0, 128],
            "name": "Lincoln",
            "id": 42,
        })
        _process_messages(client_state, q)
        assert client_state.my_color == [255, 0, 128]
        assert client_state.my_name == "Lincoln"
        assert client_state.my_id == 42

    def test_color_assign_defaults(self, client_state):
        q = self._queue({"type": "color_assign", "color": [0, 0, 0]})
        _process_messages(client_state, q)
        assert client_state.my_name == ""
        assert client_state.my_id == 0

    def test_user_list(self, client_state):
        users = [
            {"id": 1, "name": "Washington", "color": [255, 0, 0]},
            {"id": 2, "name": "Adams", "color": [0, 255, 0]},
        ]
        q = self._queue({"type": "user_list", "users": users})
        _process_messages(client_state, q)
        assert len(client_state.users) == 2
        assert client_state.users[0]["name"] == "Washington"

    def test_draw_adds_stroke(self, client_state):
        q = self._queue({
            "type": "draw",
            "color": [255, 0, 0],
            "points": [[10, 20], [30, 40]],
            "width": 6,
            "name": "Grant",
        })
        _process_messages(client_state, q)
        assert len(client_state.strokes.strokes) == 1
        assert client_state.strokes.strokes[0].name == "Grant"

    def test_draw_history(self, client_state):
        strokes = [
            {"color": [255, 0, 0], "points": [[0, 0]], "width": 2, "name": "a"},
            {"color": [0, 255, 0], "points": [[5, 5]], "width": 4, "name": "b"},
        ]
        q = self._queue({"type": "draw_history", "strokes": strokes})
        _process_messages(client_state, q)
        assert len(client_state.strokes.strokes) == 2

    def test_clear_doodles(self, client_state):
        client_state.strokes.add({"color": [0, 0, 0], "points": [[0, 0]]})
        q = self._queue({"type": "clear_doodles"})
        _process_messages(client_state, q)
        assert len(client_state.strokes.strokes) == 0

    def test_processes_multiple_messages_in_order(self, client_state):
        q = self._queue(
            {"type": "color_assign", "color": [1, 2, 3], "name": "A", "id": 1},
            {"type": "user_list", "users": [{"id": 1, "name": "A", "color": [1, 2, 3]}]},
        )
        _process_messages(client_state, q)
        assert client_state.my_name == "A"
        assert len(client_state.users) == 1

    def test_queue_is_drained(self, client_state):
        q = self._queue(
            {"type": "color_assign", "color": [0, 0, 0]},
            {"type": "color_assign", "color": [1, 1, 1]},
        )
        _process_messages(client_state, q)
        assert len(q) == 0


class TestUpdateHover:
    def test_no_hover_when_drawing(self, client_state):
        client_state.drawing = True
        _update_hover(client_state, (400, 300))
        assert client_state.hover_name is None

    def test_no_hover_off_canvas(self, client_state):
        # No image loaded, so nothing is on canvas
        _update_hover(client_state, (400, 300))
        assert client_state.hover_name is None

    def test_hover_detects_stroke(self, client_state):
        client_state.set_image(800, 600, make_png_bytes(800, 600))
        client_state.strokes.add({
            "color": [255, 0, 0],
            "points": [[400, 300], [500, 300]],
            "width": 10,
            "name": "Kennedy",
        })
        ox, oy = client_state.img_offset
        _update_hover(client_state, (ox + 450, oy + 300))
        assert client_state.hover_name == "Kennedy"
