"""Tests for Stroke model and StrokeStore: add, clear, render, and hit-testing."""

import pygame
import pytest
from pydantic import ValidationError

from client.strokes import Stroke, StrokeStore


class TestStrokeModel:
    def test_required_fields(self):
        s = Stroke(color=(255, 0, 0), points=[[0, 0], [10, 10]])
        assert s.color == (255, 0, 0)
        assert len(s.points) == 2

    def test_defaults(self):
        s = Stroke(color=(0, 0, 0), points=[[0, 0]])
        assert s.width == 4
        assert s.name == ""

    def test_custom_values(self):
        s = Stroke(color=(0, 255, 0), points=[[1, 2]], width=10, name="Lincoln")
        assert s.width == 10
        assert s.name == "Lincoln"


class TestStrokeStoreAdd:
    def test_add_from_dict(self):
        store = StrokeStore()
        store.add({"color": [255, 0, 0], "points": [[0, 0], [5, 5]], "width": 6, "name": "test"})
        assert len(store.strokes) == 1
        assert store.strokes[0].color == (255, 0, 0)
        assert store.strokes[0].width == 6
        assert store.strokes[0].name == "test"

    def test_add_defaults_width_and_name(self):
        store = StrokeStore()
        store.add({"color": [0, 0, 255], "points": [[1, 1]]})
        assert store.strokes[0].width == 4
        assert store.strokes[0].name == ""

    def test_marks_dirty_on_add(self):
        store = StrokeStore()
        store._dirty = False
        store.add({"color": [0, 0, 0], "points": [[0, 0]]})
        assert store._dirty is True

    def test_multiple_adds_accumulate(self):
        store = StrokeStore()
        for i in range(5):
            store.add({"color": [i, i, i], "points": [[i, i]]})
        assert len(store.strokes) == 5


class TestStrokeStoreClear:
    def test_clear_removes_all_strokes(self):
        store = StrokeStore()
        store.add({"color": [0, 0, 0], "points": [[0, 0]]})
        store.add({"color": [1, 1, 1], "points": [[1, 1]]})
        store.clear()
        assert len(store.strokes) == 0

    def test_clear_marks_dirty(self):
        store = StrokeStore()
        store._dirty = False
        store.clear()
        assert store._dirty is True


class TestStrokeStoreRender:
    def test_returns_surface_of_correct_size(self):
        store = StrokeStore()
        store.add({"color": [255, 0, 0], "points": [[10, 10], [20, 20]]})
        surf = store.render(640, 480, 1.0, (0, 0))
        assert surf.get_size() == (640, 480)

    def test_cached_surface_reused_when_clean(self):
        store = StrokeStore()
        store.add({"color": [255, 0, 0], "points": [[10, 10], [20, 20]]})
        surf1 = store.render(640, 480, 1.0, (0, 0))
        surf2 = store.render(640, 480, 1.0, (0, 0))
        assert surf1 is surf2

    def test_cache_invalidated_on_dirty(self):
        store = StrokeStore()
        store.add({"color": [255, 0, 0], "points": [[10, 10], [20, 20]]})
        surf1 = store.render(640, 480, 1.0, (0, 0))
        store.mark_dirty()
        surf2 = store.render(640, 480, 1.0, (0, 0))
        assert surf1 is not surf2

    def test_cache_invalidated_on_resize(self):
        store = StrokeStore()
        store.add({"color": [255, 0, 0], "points": [[10, 10], [20, 20]]})
        surf1 = store.render(640, 480, 1.0, (0, 0))
        surf2 = store.render(800, 600, 1.0, (0, 0))
        assert surf1 is not surf2

    def test_renders_single_point_as_circle(self):
        store = StrokeStore()
        store.add({"color": [255, 0, 0], "points": [[50, 50]]})
        surf = store.render(100, 100, 1.0, (0, 0))
        # The pixel at the dot center should have red
        assert surf.get_at((50, 50))[0] > 0

    def test_render_with_scale_and_offset(self):
        store = StrokeStore()
        store.add({"color": [0, 255, 0], "points": [[0, 0], [100, 0]], "width": 4})
        surf = store.render(200, 200, 0.5, (10, 10))
        # At scale 0.5 with offset (10,10), the stroke runs from (10,10) to (60,10)
        assert surf.get_at((30, 10))[1] > 0  # green channel

    def test_empty_store_renders_transparent(self):
        store = StrokeStore()
        surf = store.render(100, 100, 1.0, (0, 0))
        assert surf.get_at((50, 50))[3] == 0  # fully transparent


class TestStrokeStoreRenderLive:
    def test_draws_on_surface(self):
        store = StrokeStore()
        surf = pygame.Surface((100, 100), pygame.SRCALPHA)
        store.render_live(surf, [[10, 10], [90, 10]], [255, 0, 0], 4, 1.0, (0, 0))
        assert surf.get_at((50, 10))[0] > 0

    def test_single_point_is_noop(self):
        store = StrokeStore()
        surf = pygame.Surface((100, 100), pygame.SRCALPHA)
        store.render_live(surf, [[50, 50]], [255, 0, 0], 4, 1.0, (0, 0))
        # Single point should not draw anything (needs >= 2 points for lines)
        assert surf.get_at((50, 50))[3] == 0


class TestStrokeStoreHitTest:
    def test_hit_on_stroke_returns_name(self):
        store = StrokeStore()
        store.add({"color": [255, 0, 0], "points": [[0, 0], [100, 0]], "width": 4, "name": "Lincoln"})
        assert store.hit_test(50, 0) == "Lincoln"

    def test_miss_returns_none(self):
        store = StrokeStore()
        store.add({"color": [255, 0, 0], "points": [[0, 0], [100, 0]], "width": 4, "name": "Lincoln"})
        assert store.hit_test(50, 100) is None

    def test_empty_store_returns_none(self):
        store = StrokeStore()
        assert store.hit_test(50, 50) is None

    def test_topmost_stroke_wins(self):
        store = StrokeStore()
        store.add({"color": [255, 0, 0], "points": [[0, 50], [100, 50]], "width": 10, "name": "bottom"})
        store.add({"color": [0, 255, 0], "points": [[0, 50], [100, 50]], "width": 10, "name": "top"})
        assert store.hit_test(50, 50) == "top"

    def test_hit_on_single_point_stroke(self):
        store = StrokeStore()
        store.add({"color": [255, 0, 0], "points": [[50, 50]], "width": 4, "name": "dot"})
        assert store.hit_test(50, 50) == "dot"

    def test_hit_within_tolerance(self):
        store = StrokeStore()
        store.add({"color": [255, 0, 0], "points": [[50, 50], [100, 50]], "width": 2, "name": "thin"})
        # STROKE_HIT_TOLERANCE is 8, width/2 is 1, so effective radius = 9
        assert store.hit_test(50, 58) == "thin"
        assert store.hit_test(50, 60) is None  # just outside
