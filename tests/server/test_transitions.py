"""Tests for the transition registry and built-in transition classes."""

from server.transitions import (
    TRANSITIONS,
    CrossfadeTransition,
    CutTransition,
    Transition,
    register_transition,
)


class TestTransitionRegistry:
    def test_builtin_transitions_registered(self):
        assert "cut" in TRANSITIONS
        assert "crossfade" in TRANSITIONS

    def test_registry_maps_to_classes(self):
        assert TRANSITIONS["cut"] is CutTransition
        assert TRANSITIONS["crossfade"] is CrossfadeTransition

    def test_custom_transition_registration(self):
        @register_transition("test_wipe")
        class WipeTransition(Transition):
            def start(self, old, new, w, h):
                return [{"type": "wipe"}]

        assert TRANSITIONS["test_wipe"] is WipeTransition
        # Clean up to avoid polluting other tests
        del TRANSITIONS["test_wipe"]


class TestCutTransition:
    def test_duration_is_zero(self):
        t = CutTransition()
        assert t.duration == 0

    def test_returns_single_image_sync_message(self):
        msgs = CutTransition().start("old_b64", "new_b64", 800, 600)
        assert len(msgs) == 1
        assert msgs[0]["type"] == "image_sync"
        assert msgs[0]["data"] == "new_b64"
        assert msgs[0]["width"] == 800
        assert msgs[0]["height"] == 600

    def test_ignores_old_image(self):
        msgs = CutTransition().start("anything", "new_b64", 1, 1)
        assert "old" not in str(msgs)
        assert msgs[0]["data"] == "new_b64"


class TestCrossfadeTransition:
    def test_default_duration(self):
        t = CrossfadeTransition()
        assert t.duration == 2.0

    def test_custom_duration(self):
        t = CrossfadeTransition(duration=0.5)
        assert t.duration == 0.5

    def test_returns_transition_message_with_both_images(self):
        msgs = CrossfadeTransition(duration=1.0).start("old", "new", 1920, 1080)
        assert len(msgs) == 1
        msg = msgs[0]
        assert msg["type"] == "transition"
        assert msg["transition"] == "crossfade"
        assert msg["from_data"] == "old"
        assert msg["to_data"] == "new"
        assert msg["width"] == 1920
        assert msg["height"] == 1080
        assert msg["duration"] == 1.0
