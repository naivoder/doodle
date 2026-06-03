"""Pure-math geometry helpers with zero pygame dependency."""


def scale_to_fit(img_w: int, img_h: int, target_w: int, target_h: int) -> tuple[int, int]:
    """Return (width, height) that fits the image inside the target bounds."""
    ratio = min(target_w / img_w, target_h / img_h)
    return int(img_w * ratio), int(img_h * ratio)


def point_to_segment_dist_sq(
    px: float, py: float, ax: float, ay: float, bx: float, by: float,
) -> float:
    """Squared distance from point (px, py) to segment (ax, ay)-(bx, by)."""
    dx, dy = bx - ax, by - ay
    len_sq = dx * dx + dy * dy
    if len_sq == 0:
        return (px - ax) ** 2 + (py - ay) ** 2
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / len_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return (px - proj_x) ** 2 + (py - proj_y) ** 2
