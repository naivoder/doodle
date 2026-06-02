# Doodle

Real-time shared image viewer over a local network. One machine hosts an image via WebSocket; any number of clients connect and display it using pygame. Designed to be extended into a collaborative drawing canvas.

## Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

On Jetson Nano (or other ARM/Linux), install SDL2 first:

```bash
sudo apt-get install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
```

## Run

**Server** (on the host machine):

```bash
python server.py sample.png
```

**Client** (on any machine):

```bash
python client.py ws://<server_ip>:8765
```

For a local client on the same machine as the server:

```bash
python client.py
```
