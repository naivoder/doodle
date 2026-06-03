# Doodle

Real-time collaborative drawing canvas over WebSocket. One machine hosts a slideshow of images; any number of clients connect with pygame to doodle on them together. Each client is assigned a US president's name (or brings their own).

## Install

First, install [pixi](https://pixi.sh) if you don't have it:

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

Then install the project dependencies:

```bash
pixi install
```

On Jetson Nano (or other ARM/Linux), install SDL2 first:

```bash
sudo apt-get install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
```

## Run

**Server** (on the host machine):

```bash
pixi run serve                                         # serves sample.png on port 8765
pixi run serve -- images/                              # serve a directory of images
pixi run serve -- pic.png --transition crossfade --interval 30
```

**Client** (on any machine):

```bash
pixi run play                                          # connect to localhost:8765
pixi run play -- ws://<server_ip>:8765                 # connect to remote server
pixi run play -- ws://<server_ip>:8765 --name "My Name"  # with custom username
```

Without `--name`, you'll be randomly assigned a US president.

## Test

```bash
pixi run test
```

## Project Structure

```text
server/                  # WebSocket server package
  transitions.py         # Slide transition registry (cut, crossfade)
  images.py              # Image loading and directory discovery
  presidents.py          # US president names for random assignment
  state.py               # ServerState and Pydantic ClientInfo model
  handler.py             # Connection handler, broadcast, slideshow loop
  __main__.py            # CLI entrypoint

client/                  # Pygame client package
  constants.py           # UI layout and rendering constants
  geometry.py            # Scale-to-fit and point-to-segment math
  strokes.py             # Pydantic Stroke model and StrokeStore
  ui.py                  # Frosted-glass UI widgets
  state.py               # ClientState (image, drawing, UI panels)
  network.py             # WebSocket reader task
  app.py                 # Main event/render loop
  __main__.py            # CLI entrypoint

tests/                   # 113 tests covering server and client logic
```
