"""UI layout and rendering constants for the doodle client."""

from typing import Final

TARGET_WIDTH: Final[int] = 1280
TARGET_HEIGHT: Final[int] = 960

UI_FONT_SIZE: Final[int] = 14
UI_PADDING: Final[int] = 10
UI_CORNER_RADIUS: Final[int] = 12
COLOR_SWATCH_SIZE: Final[int] = 22
COLOR_PICKER_COLUMNS: Final[int] = 6
ICON_SIZE: Final[int] = 32
THICKNESS_OPTIONS: Final[list[int]] = [2, 4, 6, 10, 16, 24]
STROKE_HIT_TOLERANCE: Final[int] = 8

GLASS_BG: Final[tuple[int, int, int, int]] = (255, 255, 255, 40)
GLASS_BORDER: Final[tuple[int, int, int, int]] = (255, 255, 255, 80)
GLASS_TEXT: Final[tuple[int, int, int]] = (255, 255, 255)
GLASS_HIGHLIGHT: Final[tuple[int, int, int, int]] = (255, 255, 255, 60)
TOOLTIP_BG: Final[tuple[int, int, int, int]] = (30, 30, 30, 200)

PICKER_COLORS: Final[list[list[int]]] = [
    [231, 76, 60],   [192, 57, 43],   [211, 84, 0],
    [243, 156, 18],  [241, 196, 15],  [39, 174, 96],
    [46, 134, 193],  [41, 128, 185],  [142, 68, 173],
    [26, 188, 156],  [22, 160, 133],  [52, 73, 94],
    [236, 240, 241], [189, 195, 199], [127, 140, 141],
    [44, 62, 80],    [255, 255, 255], [30, 30, 30],
]
