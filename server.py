#!/usr/bin/env python3
"""Entry point for the doodle server. Run: python server.py [image_path]"""

import argparse
import asyncio

from server.__main__ import main
from server.transitions import TRANSITIONS

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
