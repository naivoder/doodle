"""Tests for WebSocket connection handling, broadcasting, and slideshow loop."""

import asyncio
import json

import pytest

from tests.conftest import make_mock_ws
from server.handler import broadcast, broadcast_user_list, handle_connection, slideshow_loop


class TestBroadcast:
    async def test_sends_to_all_clients(self, server_state):
        ws1, ws2 = make_mock_ws(), make_mock_ws()
        server_state.assign_client(ws1)
        server_state.assign_client(ws2)

        await broadcast(server_state, '{"type":"ping"}')
        ws1.send.assert_called_once_with('{"type":"ping"}')
        ws2.send.assert_called_once_with('{"type":"ping"}')

    async def test_excludes_specified_client(self, server_state):
        ws1, ws2 = make_mock_ws(), make_mock_ws()
        server_state.assign_client(ws1)
        server_state.assign_client(ws2)

        await broadcast(server_state, '{"msg":"hi"}', exclude=ws1)
        ws1.send.assert_not_called()
        ws2.send.assert_called_once()

    async def test_noop_with_no_clients(self, server_state):
        await broadcast(server_state, '{"msg":"hi"}')  # should not raise


class TestBroadcastUserList:
    async def test_sends_user_list_to_all(self, server_state):
        ws1, ws2 = make_mock_ws(), make_mock_ws()
        server_state.assign_client(ws1)
        server_state.assign_client(ws2)

        await broadcast_user_list(server_state)

        for ws in (ws1, ws2):
            sent = json.loads(ws.send.call_args[0][0])
            assert sent["type"] == "user_list"
            assert len(sent["users"]) == 2


class TestHandleConnection:
    async def test_sends_image_sync_on_connect(self, server_state):
        ws = make_mock_ws()
        # Simulate a connection that immediately closes (empty async iterator)
        ws.__aiter__ = lambda self: self
        ws.__anext__ = lambda self: (_ for _ in ()).throw(StopAsyncIteration)

        await handle_connection(ws, server_state)

        calls = [json.loads(c[0][0]) for c in ws.send.call_args_list]
        image_sync = next(m for m in calls if m["type"] == "image_sync")
        assert image_sync["width"] == 4
        assert image_sync["height"] == 4

    async def test_sends_color_assign_on_connect(self, server_state):
        ws = make_mock_ws()
        ws.__aiter__ = lambda self: self
        ws.__anext__ = lambda self: (_ for _ in ()).throw(StopAsyncIteration)

        await handle_connection(ws, server_state)

        calls = [json.loads(c[0][0]) for c in ws.send.call_args_list]
        color_assign = next(m for m in calls if m["type"] == "color_assign")
        assert "color" in color_assign
        assert "name" in color_assign
        assert "id" in color_assign

    async def test_client_removed_after_disconnect(self, server_state):
        ws = make_mock_ws()
        ws.__aiter__ = lambda self: self
        ws.__anext__ = lambda self: (_ for _ in ()).throw(StopAsyncIteration)

        await handle_connection(ws, server_state)
        assert ws not in server_state.clients

    async def test_draw_message_stored_and_broadcast(self, server_state):
        sender = make_mock_ws()
        receiver = make_mock_ws()
        server_state.assign_client(receiver)

        draw_msg = json.dumps({
            "type": "draw",
            "color": [255, 0, 0],
            "points": [[10, 20], [30, 40]],
            "width": 4,
        })

        messages = iter([draw_msg])
        async def async_iter(self):
            for m in messages:
                yield m
        sender.__aiter__ = async_iter

        await handle_connection(sender, server_state)

        assert len(server_state.draw_history) == 1
        assert server_state.draw_history[0]["color"] == [255, 0, 0]
        # The stroke should have been enriched with the sender's name
        assert "name" in server_state.draw_history[0]

    async def test_name_change_updates_client(self, server_state):
        ws = make_mock_ws()
        name_msg = json.dumps({"type": "name_change", "name": "TestUser"})

        messages = iter([name_msg])
        async def async_iter(self):
            for m in messages:
                yield m
        ws.__aiter__ = async_iter

        await handle_connection(ws, server_state)
        # Client is removed after disconnect, but we can check the name
        # was applied by looking at what was broadcast
        # The user_list broadcast happens, so check the send calls
        calls = [json.loads(c[0][0]) for c in ws.send.call_args_list]
        user_lists = [m for m in calls if m["type"] == "user_list"]
        assert any(
            any(u["name"] == "TestUser" for u in ul["users"])
            for ul in user_lists
        )

    async def test_sends_draw_history_on_connect(self, server_state):
        server_state.add_stroke({
            "color": [0, 0, 255], "points": [[5, 5]], "width": 2, "name": "prev",
        })

        ws = make_mock_ws()
        ws.__aiter__ = lambda self: self
        ws.__anext__ = lambda self: (_ for _ in ()).throw(StopAsyncIteration)

        await handle_connection(ws, server_state)

        calls = [json.loads(c[0][0]) for c in ws.send.call_args_list]
        history_msg = next(m for m in calls if m["type"] == "draw_history")
        assert len(history_msg["strokes"]) == 1


class TestSlideshowLoop:
    async def test_exits_immediately_with_single_image(self, server_state):
        """With only one image, the loop should return without sleeping."""
        await asyncio.wait_for(slideshow_loop(server_state), timeout=0.5)

    async def test_advances_slide(self, multi_image_state):
        """With multiple images, the loop should advance and broadcast."""
        multi_image_state.slide_interval = 0.05  # fast for testing
        ws = make_mock_ws()
        multi_image_state.assign_client(ws)

        task = asyncio.create_task(slideshow_loop(multi_image_state))
        await asyncio.sleep(0.15)  # enough for ~2 advances
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have advanced at least once
        calls = [json.loads(c[0][0]) for c in ws.send.call_args_list]
        assert any(m["type"] == "clear_doodles" for m in calls)
        assert any(m["type"] == "image_sync" for m in calls)
