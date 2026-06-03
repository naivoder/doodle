import argparse
import asyncio

from .app import run_client


def main():
    parser = argparse.ArgumentParser(description="Doodle client")
    parser.add_argument(
        "server",
        nargs="?",
        default="ws://localhost:8765",
        help="WebSocket server URL (default: ws://localhost:8765)",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Your display name (default: randomly assigned US president)",
    )
    args = parser.parse_args()
    asyncio.run(run_client(args.server, username=args.name))


if __name__ == "__main__":
    main()
