"""Tests for geometry helpers: scaling and point-to-segment distance."""

import math

from client.geometry import point_to_segment_dist_sq, scale_to_fit


class TestScaleToFit:
    def test_exact_fit(self):
        assert scale_to_fit(800, 600, 800, 600) == (800, 600)

    def test_scales_down_wide_image(self):
        w, h = scale_to_fit(1600, 600, 800, 600)
        assert w == 800
        assert h <= 600

    def test_scales_down_tall_image(self):
        w, h = scale_to_fit(600, 1200, 800, 600)
        assert h == 600
        assert w <= 800

    def test_scales_up_small_image(self):
        w, h = scale_to_fit(100, 100, 800, 600)
        # Should fill available space (limited by height for square in landscape)
        assert w == 600
        assert h == 600

    def test_preserves_aspect_ratio(self):
        w, h = scale_to_fit(1920, 1080, 640, 480)
        ratio_original = 1920 / 1080
        ratio_scaled = w / h
        assert abs(ratio_original - ratio_scaled) < 0.02

    def test_returns_integers(self):
        w, h = scale_to_fit(1000, 333, 500, 500)
        assert isinstance(w, int)
        assert isinstance(h, int)


class TestPointToSegmentDistSq:
    def test_point_on_segment_returns_zero(self):
        assert point_to_segment_dist_sq(5, 0, 0, 0, 10, 0) == 0.0

    def test_point_at_endpoint(self):
        assert point_to_segment_dist_sq(0, 0, 0, 0, 10, 0) == 0.0

    def test_perpendicular_distance(self):
        d2 = point_to_segment_dist_sq(5, 3, 0, 0, 10, 0)
        assert d2 == 9.0  # 3^2

    def test_distance_beyond_endpoint(self):
        d2 = point_to_segment_dist_sq(15, 0, 0, 0, 10, 0)
        assert d2 == 25.0  # 5^2

    def test_distance_before_start(self):
        d2 = point_to_segment_dist_sq(-3, 4, 0, 0, 10, 0)
        assert d2 == 25.0  # 3^2 + 4^2

    def test_zero_length_segment(self):
        d2 = point_to_segment_dist_sq(3, 4, 5, 5, 5, 5)
        assert d2 == (3 - 5) ** 2 + (4 - 5) ** 2

    def test_diagonal_segment(self):
        # Point (0, 1) to segment from (0, 0) to (1, 1)
        # Closest point is (0.5, 0.5), distance = sqrt(0.5)
        d2 = point_to_segment_dist_sq(0, 1, 0, 0, 1, 1)
        assert abs(d2 - 0.5) < 1e-10
