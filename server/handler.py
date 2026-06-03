import asyncio
import json

import websockets


async def broadcast(state, message_str, exclude=None):
    targets = set(state.clients) - ({exclude} if exclude else set())
    if targets:
        await asyncio.gather(*(c.send(message_str) for c in targets), return_exceptions=True)


async def broadcast_user_list(state):
    msg = json.dumps({"type": "user_list", "users": state.build_user_list()})
    await broadcast(state, msg)


async def handle_connection(websocket, state):
    color, name, cid = state.assign_client(websocket)
    remote = websocket.remote_address
    print(f"[+] {name} connected from {remote[0]}:{remote[1]}  color={color}  ({len(state.clients)} total)")

    try:
        await websocket.send(json.dumps({
            "type": "image_sync",
            "data": state.image_b64,
            "width": state.image_width,
            "height": state.image_height,
        }))

        await websocket.send(json.dumps({
            "type": "color_assign",
            "color": color,
            "name": name,
            "id": cid,
        }))

        if state.draw_history:
            await websocket.send(json.dumps({
                "type": "draw_history",
                "strokes": state.draw_history,
            }))

        await broadcast_user_list(state)

        async for message in websocket:
            data = json.loads(message)

            if data["type"] == "draw":
                data["name"] = state.clients[websocket]["name"]
                enriched = json.dumps(data)
                state.add_stroke(data)
                await broadcast(state, enriched, exclude=websocket)

            elif data["type"] == "color_change":
                new_color = data["color"]
                state.clients[websocket]["color"] = new_color
                await websocket.send(json.dumps({
                    "type": "color_assign",
                    "color": new_color,
                    "name": state.clients[websocket]["name"],
                    "id": cid,
                }))
                await broadcast_user_list(state)

            elif data["type"] == "name_change":
                new_name = data["name"][:20]
                state.clients[websocket]["name"] = new_name
                await broadcast_user_list(state)

    except websockets.ConnectionClosed:
        pass
    finally:
        state.remove_client(websocket)
        print(f"[-] {name} disconnected  ({len(state.clients)} total)")
        if state.clients:
            await broadcast_user_list(state)


async def slideshow_loop(state):
    if len(state.images) < 2:
        return
    while True:
        await asyncio.sleep(state.slide_interval)
        print(f"\n--- Advancing slideshow (image {state.current_index + 1}/{len(state.images)}) ---")
        messages = state.advance_image()
        await broadcast(state, json.dumps({"type": "clear_doodles"}))
        for msg in messages:
            await broadcast(state, json.dumps(msg))
