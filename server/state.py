import os
import random

from .images import load_image
from .presidents import PRESIDENTS
from .transitions import TRANSITIONS, CutTransition

COLOR_PALETTE = [
    [231, 76, 60],  [46, 134, 193],  [39, 174, 96],
    [243, 156, 18], [142, 68, 173],  [26, 188, 156],
    [241, 196, 15], [52, 73, 94],
]


class ServerState:

    def __init__(self, images, transition_name, slide_interval):
        self.images = images
        self.slide_interval = slide_interval
        self.transition = TRANSITIONS.get(transition_name, CutTransition)()
        self.current_index = 0

        self.image_b64 = None
        self.image_width = 0
        self.image_height = 0

        self.clients = {}
        self.next_color_index = 0
        self.next_client_id = 1
        self._used_presidents = []

        self.draw_history = []

    def _pick_president(self):
        if not self._used_presidents:
            self._used_presidents = list(PRESIDENTS)
            random.shuffle(self._used_presidents)
        return self._used_presidents.pop()

    def load_current_image(self):
        path = self.images[self.current_index]
        self.image_b64, self.image_width, self.image_height = load_image(path)
        print(f"  Image loaded: {os.path.basename(path)} ({self.image_width}x{self.image_height})")

    def advance_image(self):
        old_b64 = self.image_b64
        self.current_index = (self.current_index + 1) % len(self.images)
        self.load_current_image()
        self.draw_history.clear()
        return self.transition.start(old_b64, self.image_b64, self.image_width, self.image_height)

    def assign_client(self, ws):
        color = COLOR_PALETTE[self.next_color_index % len(COLOR_PALETTE)]
        self.next_color_index += 1
        cid = self.next_client_id
        self.next_client_id += 1
        name = self._pick_president()
        self.clients[ws] = {"color": color, "name": name, "id": cid}
        return color, name, cid

    def remove_client(self, ws):
        if ws in self.clients:
            del self.clients[ws]

    def add_stroke(self, stroke):
        self.draw_history.append(stroke)

    def build_user_list(self):
        return [{"id": c["id"], "name": c["name"], "color": c["color"]} for c in self.clients.values()]
