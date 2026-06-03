import json

import websockets


async def ws_reader(ws, msg_queue, state):
    try:
        async for raw in ws:
            msg_queue.append(json.loads(raw))
    except websockets.ConnectionClosed:
        pass
    finally:
        state.running = False
