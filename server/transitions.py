TRANSITIONS = {}


def register_transition(name):
    def decorator(cls):
        TRANSITIONS[name] = cls
        return cls
    return decorator


class Transition:
    def __init__(self, duration=1.0):
        self.duration = duration

    def start(self, old_image_b64, new_image_b64, width, height):
        raise NotImplementedError


@register_transition("cut")
class CutTransition(Transition):
    def __init__(self):
        super().__init__(duration=0)

    def start(self, old_image_b64, new_image_b64, width, height):
        return [{"type": "image_sync", "data": new_image_b64, "width": width, "height": height}]


@register_transition("crossfade")
class CrossfadeTransition(Transition):
    def __init__(self, duration=2.0):
        super().__init__(duration=duration)

    def start(self, old_image_b64, new_image_b64, width, height):
        return [{
            "type": "transition",
            "transition": "crossfade",
            "duration": self.duration,
            "from_data": old_image_b64,
            "to_data": new_image_b64,
            "width": width,
            "height": height,
        }]
