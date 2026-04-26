# Version2TrashCan

`version2trashcan` is an ESP32-focused wall-camera trash can project.

Recommended architecture:

- Raspberry Pi + fixed ceiling/wall camera
- ESP32 on the trash can
- Bluetooth commands from Pi to ESP32
- L298N motor driver connected to the ESP32

The fixed camera watches:
- the trash can
- the target object

The trash can should have two visible markers:
- front marker: pink
- back marker: green

The target object should use one detectable color:
- target: yellow by default

## How it works

1. Detect the pink front marker.
2. Detect the green back marker.
3. Compute the trash can center and heading.
4. Detect the target object.
5. Lock onto the first target.
6. Send `L`, `R`, `F`, or `S` to the controller.

## Files

- `main.py`: main wall-camera loop
- `camera_detection_test.py`: camera-only test for robot markers and target object
- `camera.py`: OpenCV/Picamera2 capture
- `detection.py`: marker and target color detection
- `controller.py`: heading math and command selection
- `transport.py`: command output to ESP32 over Bluetooth, USB serial, or stdout
- `config.py`: tuning and color ranges
- `esp32/version2trashcan_esp32.ino`: starter ESP32 Bluetooth + motor sketch

## Run

```bash
cd /Users/harp12/CSCE462-labs/version2trashcan
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 main.py
```

## Camera detection test

Before running the motors, test that the ceiling/wall camera can see the robot and target:

```bash
cd /Users/harp12/CSCE462-labs/version2trashcan
python3 camera_detection_test.py
```

The preview window should show:

- pink circle/text on the front marker
- green circle/text on the back marker
- yellow box around the target object
- measured HSV values for each detected color, next to the configured HSV range

For a terminal-only test:

```bash
python3 camera_detection_test.py --no-window
```

## Controls

- `q` or `Esc`: quit
- `r`: reset the locked target

## Default mode

The project is configured for ESP32 Bluetooth by default.

Set these values in `config.py` before running:

```python
COMMAND_TRANSPORT = "bluetooth"
BLUETOOTH_DEVICE_NAME = "Version2TrashCan"
BLUETOOTH_MAC_ADDRESS = "AA:BB:CC:DD:EE:FF"
```

## Bluetooth mode

To send commands from the Raspberry Pi directly to the ESP32 over Bluetooth RFCOMM:

```python
COMMAND_TRANSPORT = "bluetooth"
BLUETOOTH_MAC_ADDRESS = "AA:BB:CC:DD:EE:FF"
BLUETOOTH_CHANNEL = 1
```

Find the ESP32 MAC address after pairing or scanning from the Pi.

Typical Raspberry Pi steps:

```bash
bluetoothctl
scan on
pair AA:BB:CC:DD:EE:FF
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
```

Then run `python3 main.py`.

## USB serial fallback

If Bluetooth gives you trouble during bring-up, you can temporarily send commands to the ESP32 over USB serial:

```python
COMMAND_TRANSPORT = "serial"
SERIAL_PORT = "/dev/ttyUSB0"
```

## ESP32 wiring

Recommended ESP32 + L298N wiring:

- `ESP32 GPIO25` -> `IN1`
- `ESP32 GPIO26` -> `IN2`
- `ESP32 GPIO27` -> `IN3`
- `ESP32 GPIO14` -> `IN4`
- `ESP32 GPIO33` -> `ENA`
- `ESP32 GPIO32` -> `ENB`
- `ESP32 GND` -> `L298N GND`
- Motor power supply ground -> `L298N GND`
- Left motor -> `OUT1` / `OUT2`
- Right motor -> `OUT3` / `OUT4`

Important:

- Share ground between the ESP32 and the motor driver.
- Do not power the motors from the ESP32.
- Power the ESP32 from USB or a proper regulator.
- Remove the `ENA` / `ENB` jumpers on the L298N if you want PWM speed control.

## ESP32 sketch

Upload [version2trashcan_esp32.ino](/Users/harp12/CSCE462-labs/version2trashcan/esp32/version2trashcan_esp32.ino) to the ESP32. It creates a Bluetooth device named `Version2TrashCan`.

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
- The intended robot controller for this project is an ESP32.
