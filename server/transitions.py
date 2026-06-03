"""Slide transition registry. Add new transitions by subclassing and decorating."""

from __future__ import annotations

from typing import Any

type TransitionMessage = dict[str, Any]

TRANSITIONS: dict[str, type[Transition]] = {}


def register_transition(name: str):
    """Class decorator that registers a Transition subclass under ``name``."""
    def decorator[T: Transition](cls: type[T]) -> type[T]:
        TRANSITIONS[name] = cls
        return cls
    return decorator


class Transition:
    """Base class for slide transitions. Subclass and use @register_transition to extend."""

    def __init__(self, duration: float = 1.0) -> None:
        self.duration = duration

    def start(
        self, old_image_b64: str, new_image_b64: str, width: int, height: int,
    ) -> list[TransitionMessage]:
        raise NotImplementedError


@register_transition("cut")
class CutTransition(Transition):
    """Instant cut — blink and you'll miss it."""

    def __init__(self) -> None:
        super().__init__(duration=0)

    def start(
        self, old_image_b64: str, new_image_b64: str, width: int, height: int,
    ) -> list[TransitionMessage]:
        return [{"type": "image_sync", "data": new_image_b64, "width": width, "height": height}]


@register_transition("crossfade")
class CrossfadeTransition(Transition):
    """Smooth crossfade between slides."""

    def __init__(self, duration: float = 2.0) -> None:
        super().__init__(duration=duration)

    def start(
        self, old_image_b64: str, new_image_b64: str, width: int, height: int,
    ) -> list[TransitionMessage]:
        return [{
            "type": "transition",
            "transition": "crossfade",
            "duration": self.duration,
            "from_data": old_image_b64,
            "to_data": new_image_b64,
            "width": width,
            "height": height,
        }]
