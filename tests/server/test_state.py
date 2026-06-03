"""Tests for ServerState: client management, president assignment, slideshow cycling."""

from tests.conftest import make_mock_ws
from server.presidents import PRESIDENTS
from server.state import ClientInfo, ServerState


class TestClientInfo:
    def test_fields(self):
        info = ClientInfo(color=[255, 0, 0], name="Lincoln", id=1)
        assert info.color == [255, 0, 0]
        assert info.name == "Lincoln"
        assert info.id == 1

    def test_model_dump(self):
        info = ClientInfo(color=[0, 255, 0], name="Grant", id=7)
        d = info.model_dump()
        assert d == {"color": [0, 255, 0], "name": "Grant", "id": 7}

    def test_mutable_fields(self):
        info = ClientInfo(color=[0, 0, 0], name="Adams", id=2)
        info.name = "Jefferson"
        info.color = [1, 2, 3]
        assert info.name == "Jefferson"
        assert info.color == [1, 2, 3]


class TestAssignClient:
    def test_returns_client_info(self, server_state):
        ws = make_mock_ws()
        info = server_state.assign_client(ws)
        assert isinstance(info, ClientInfo)

    def test_assigns_president_name(self, server_state):
        ws = make_mock_ws()
        info = server_state.assign_client(ws)
        assert info.name in PRESIDENTS

    def test_sequential_ids(self, server_state):
        ws1, ws2 = make_mock_ws(), make_mock_ws()
        info1 = server_state.assign_client(ws1)
        info2 = server_state.assign_client(ws2)
        assert info2.id == info1.id + 1

    def test_color_cycles_through_palette(self, server_state):
        from server.state import COLOR_PALETTE
        clients = [make_mock_ws() for _ in range(len(COLOR_PALETTE) + 1)]
        infos = [server_state.assign_client(ws) for ws in clients]
        # First and (palette_size + 1)th client should get the same color
        assert infos[0].color == infos[len(COLOR_PALETTE)].color

    def test_no_duplicate_presidents_until_pool_exhausted(self, server_state):
        clients = [make_mock_ws() for _ in range(len(PRESIDENTS))]
        names = [server_state.assign_client(ws).name for ws in clients]
        assert len(set(names)) == len(PRESIDENTS)

    def test_president_pool_replenishes(self, server_state):
        """After exhausting all 45 presidents, the pool reshuffles and continues."""
        clients = [make_mock_ws() for _ in range(len(PRESIDENTS) + 1)]
        names = [server_state.assign_client(ws).name for ws in clients]
        assert names[-1] in PRESIDENTS


class TestRemoveClient:
    def test_removes_tracked_client(self, server_state):
        ws = make_mock_ws()
        server_state.assign_client(ws)
        assert ws in server_state.clients
        server_state.remove_client(ws)
        assert ws not in server_state.clients

    def test_removing_unknown_client_is_noop(self, server_state):
        ws = make_mock_ws()
        server_state.remove_client(ws)  # should not raise


class TestBuildUserList:
    def test_empty_when_no_clients(self, server_state):
        assert server_state.build_user_list() == []

    def test_includes_all_clients(self, server_state):
        ws1, ws2 = make_mock_ws(), make_mock_ws()
        server_state.assign_client(ws1)
        server_state.assign_client(ws2)
        users = server_state.build_user_list()
        assert len(users) == 2
        assert all({"id", "name", "color"} == set(u.keys()) for u in users)


class TestDrawHistory:
    def test_add_stroke_appends(self, server_state):
        stroke = {"color": [255, 0, 0], "points": [[0, 0], [1, 1]], "width": 4}
        server_state.add_stroke(stroke)
        assert len(server_state.draw_history) == 1
        assert server_state.draw_history[0] is stroke

    def test_history_clears_on_advance(self, multi_image_state):
        multi_image_state.add_stroke({"color": [0, 0, 0], "points": [[0, 0]]})
        assert len(multi_image_state.draw_history) == 1
        multi_image_state.advance_image()
        assert len(multi_image_state.draw_history) == 0


class TestSlideshow:
    def test_load_current_image_sets_dimensions(self, server_state):
        assert server_state.image_width == 4
        assert server_state.image_height == 4
        assert len(server_state.image_b64) > 0

    def test_advance_cycles_index(self, multi_image_state):
        initial = multi_image_state.current_index
        multi_image_state.advance_image()
        assert multi_image_state.current_index == initial + 1

    def test_advance_wraps_around(self, multi_image_state):
        n = len(multi_image_state.images)
        for _ in range(n):
            multi_image_state.advance_image()
        assert multi_image_state.current_index == 0

    def test_advance_returns_transition_messages(self, multi_image_state):
        msgs = multi_image_state.advance_image()
        assert isinstance(msgs, list)
        assert len(msgs) > 0
        assert msgs[0]["type"] == "image_sync"  # cut transition
