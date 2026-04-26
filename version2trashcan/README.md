# Version2TrashCan

`version2trashcan` is an ESP32-focused wall-camera trash can project.

Recommended architecture:

- Raspberry Pi + fixed ceiling/wall camera
- ESP32/Arduino motor controller on the trash can
- Bluetooth commands from Pi to ESP32
- L298N motor driver connected to the ESP32

The fixed camera watches:
- the trash can
- the target object

The trash can should have two visible markers:
- front marker: pink
- back marker: green

The target object should use one detectable color:
- target: tennis ball

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
- `movement_test.py`: safe movement-only test for `F`, `L`, `R`, and `S`
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
- yellow box around the tennis ball target
- measured HSV values for each detected color, next to the configured HSV range

You can also left-click the preview image to sample the color under the cursor. The test will print and display:

- clicked pixel location
- average BGR/HSV from a small patch
- suggested HSV range from recent clicks

Press `c` to clear click samples.

For a terminal-only test:

```bash
python3 camera_detection_test.py --no-window
```

If colors look swapped in the preview, test the red/blue channel fix:

```bash
python3 camera_detection_test.py --camera-color-mode rgb_to_bgr
```

If that makes the colors look correct, set this in `config.py`:

```python
CAMERA_COLOR_MODE = "rgb_to_bgr"
```

## Controls

- `q` or `Esc`: quit
- `r`: reset the locked target
- `h`: set the current robot position as home

## Movement test

Test movement without using the camera:

```bash
cd /Users/harp12/CSCE462-labs/version2trashcan
python3 movement_test.py
```

That runs `F`, `L`, and `R` for 2 seconds each, sending `S` after each command.

To test one command:

```bash
python3 movement_test.py F --duration 1.0
python3 movement_test.py L --duration 1.0
python3 movement_test.py R --duration 1.0
python3 movement_test.py S
```

To run the ESP32's built-in motor self-test:

```bash
python3 movement_test.py T
```

The ESP32 Serial Monitor should print `SELF TEST START`, `FORWARD`, `LEFT`, `RIGHT`, and `STOP`.

## Turn calibration test

Test the same angle-based turn strength that `main.py` sends:

```bash
python3 turn_calibration_test.py L --angle 30 --duration 1.0
python3 turn_calibration_test.py L --angle 60 --duration 1.0
python3 turn_calibration_test.py L --angle 90 --duration 1.0
```

To bypass the angle math and test raw turn strength:

```bash
python3 turn_calibration_test.py R --strength 25 --duration 1.0
python3 turn_calibration_test.py R --strength 50 --duration 1.0
python3 turn_calibration_test.py R --strength 75 --duration 1.0
```

## Default mode

The project is configured for ESP32 Bluetooth by default. The Raspberry Pi runs the camera code and sends `F`, `L`, `R`, or `S` over Bluetooth. The ESP32/Arduino sketch receives those commands and drives the L298N motor driver.

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
- `TURN_STRENGTH_SCALE`
- `MIN_TURN_STRENGTH`
- `MAX_TURN_STRENGTH`
- `TARGET_COLLECTED_DISTANCE_PX`
- `TARGET_COLLECTED_SECONDS`
- `RETURN_HOME_WHEN_TARGET_COLLECTED`
- `RETURN_HOME_WHEN_TARGET_LOST`
- `HOME_STOP_PX`
- `LOCK_MAX_JUMP_PX`

Turn tuning:

- If turns overshoot, lower `TURN_STRENGTH_SCALE` or `MAX_TURN_STRENGTH`.
- If turns are too weak, raise `TURN_STRENGTH_SCALE` or `MIN_TURN_STRENGTH`.

## Notes

- This version is designed for a fixed wall or overhead camera.
- It is much easier to debug than a robot-mounted camera.
- Use strong lighting and bright markers for the first demo.
- The intended robot controller for this project is an ESP32.
