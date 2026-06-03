import argparse
import asyncio
import signal

import websockets

from .handler import handle_connection, slideshow_loop
from .images import discover_images
from .state import ServerState
from .transitions import TRANSITIONS


async def main(host, port, image_path, transition_name, slide_interval):
    images = discover_images(image_path)
    if not images:
        print(f"Error: no images found at '{image_path}'")
        return

    print(f"Found {len(images)} image(s) in slideshow")
    state = ServerState(images, transition_name, slide_interval)
    state.load_current_image()

    stop = asyncio.get_event_loop().create_future()

    def _signal_handler():
        if not stop.done():
            stop.set_result(None)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    async with websockets.serve(
        lambda ws: handle_connection(ws, state), host, port, max_size=20 * 1024 * 1024
    ):
        print(f"Server listening on ws://{host}:{port}")
        if len(images) > 1:
            print(f"Slideshow: {slide_interval}s per image, transition: {transition_name}")
        print("Press Ctrl+C to stop.\n")

        slide_task = asyncio.create_task(slideshow_loop(state))

        try:
            await stop
        finally:
            slide_task.cancel()
            try:
                await slide_task
            except asyncio.CancelledError:
                pass

    print("\nServer shut down.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Doodle slideshow server")
    parser.add_argument(
        "image",
        nargs="?",
        default="sample.png",
        help="Path to an image file or directory of images (default: sample.png)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    parser.add_argument(
        "--transition",
        default="cut",
        choices=sorted(TRANSITIONS.keys()),
        help="Transition effect between slides (default: cut)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds between slide changes (default: 60)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port, args.image, args.transition, args.interval))
