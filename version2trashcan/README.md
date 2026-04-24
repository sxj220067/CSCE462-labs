# Version2TrashCan

`version2trashcan` is a simpler wall-camera version of the trash can project.

The fixed camera watches:
- the trash can
- the target object

The trash can should have two visible markers:
- front marker: red
- back marker: blue

The target object should use one detectable color:
- target: green by default

## How it works

1. Detect the red front marker.
2. Detect the blue back marker.
3. Compute the trash can center and heading.
4. Detect the target object.
5. Lock onto the first target.
6. Send `L`, `R`, `F`, or `S` to the controller.

## Files

- `main.py`: main wall-camera loop
- `camera.py`: OpenCV/Picamera2 capture
- `detection.py`: marker and target color detection
- `controller.py`: heading math and command selection
- `transport.py`: stdout or serial output for Arduino
- `config.py`: tuning and color ranges
- `arduino/version2trashcan_controller.ino`: starter Arduino sketch

## Run

```bash
cd /Users/harp12/CSCE462-labs/version2trashcan
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 main.py
```

## Controls

- `q` or `Esc`: quit
- `r`: reset the locked target

## Serial mode

By default the project prints commands to stdout.

To send commands to an Arduino over USB serial, set in `config.py`:

```python
COMMAND_TRANSPORT = "serial"
SERIAL_PORT = "/dev/ttyUSB0"
```

## Tuning

You will likely need to tune these first in `config.py`:

- `FRONT_MARKER_HSV_RANGES`
- `BACK_MARKER_HSV_RANGES`
- `TARGET_HSV_RANGES`
- `DISTANCE_STOP_PX`
- `HEADING_ALIGNMENT_DEG`
- `LOCK_MAX_JUMP_PX`

## Notes

- This version is designed for a fixed wall or overhead camera.
- It is much easier to debug than a robot-mounted camera.
- Use strong lighting and bright markers for the first demo.
