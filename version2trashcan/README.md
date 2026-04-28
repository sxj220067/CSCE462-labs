# Version2TrashCan

`version2trashcan` is a Raspberry Pi wall-camera trash can project.

Recommended architecture:

- Raspberry Pi + fixed ceiling/wall camera
- Raspberry Pi motor controller on the trash can
- Bluetooth commands from camera Pi to motor Pi
- Direct GPIO commands from motor Pi to L298N
- L298N motor driver connected to the Pi

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
- `transport.py`: command output to Raspberry Pi GPIO, ESP32 Bluetooth/USB serial, or stdout
- `motor_bluetooth_server.py`: Bluetooth motor receiver for a separate motor-control Raspberry Pi
- `motor_server.py`: TCP network motor receiver for a separate motor-control Raspberry Pi
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

The project is configured for a two-Raspberry-Pi Bluetooth setup by default. The camera Pi runs the camera code and sends motor commands over Bluetooth. The motor Pi receives those commands and drives the L298N motor driver directly with GPIO.

Set these values in `config.py` before running:

```python
COMMAND_TRANSPORT = "pi_bluetooth"
MOTOR_BLUETOOTH_ADDRESS = "AA:BB:CC:DD:EE:FF"
MOTOR_BLUETOOTH_CHANNEL = 1
```

Pair the Pis first. On the motor Pi, find its Bluetooth address:

```bash
bluetoothctl show
```

Use the `Controller XX:XX:XX:XX:XX:XX` address as `MOTOR_BLUETOOTH_ADDRESS` in `config.py` on the camera Pi.

On both Pis, make Bluetooth discoverable/pairable while pairing:

```bash
bluetoothctl
power on
agent on
default-agent
discoverable on
pairable on
```

From the camera Pi's `bluetoothctl`, pair and trust the motor Pi:

```text
scan on
pair AA:BB:CC:DD:EE:FF
trust AA:BB:CC:DD:EE:FF
scan off
quit
```

On the motor Pi, run the Bluetooth motor server:

```bash
cd /Users/harp12/CSCE462-labs/version2trashcan
python3 motor_bluetooth_server.py
```

On the camera Pi, run:

```bash
cd /Users/harp12/CSCE462-labs/version2trashcan
python3 main.py
```

## Raspberry Pi GPIO mode

Recommended motor Pi + L298N wiring uses BCM GPIO numbers:

- `GPIO25` -> `IN1`
- `GPIO26` -> `IN2`
- `GPIO27` -> `IN3`
- `GPIO14` -> `IN4`
- `GPIO13` -> `ENA`
- `GPIO12` -> `ENB`
- `Pi GND` -> `L298N GND`
- Motor power supply ground -> `L298N GND`
- Left motor -> `OUT1` / `OUT2`
- Right motor -> `OUT3` / `OUT4`

Important:

- Share ground between the Pi and the motor driver.
- Do not power the motors from the Pi.
- Remove the `ENA` / `ENB` jumpers on the L298N if you want PWM speed control.
- Install GPIO support on the Pi if needed: `sudo apt install python3-rpi.gpio`.

If the camera and motors are on the same Pi, use:

```python
COMMAND_TRANSPORT = "gpio"
```

If you want Wi-Fi/TCP instead of Bluetooth, use:

```python
COMMAND_TRANSPORT = "tcp"
MOTOR_SERVER_HOST = "motorpi.local"
MOTOR_SERVER_PORT = 4620
```

Then run `python3 motor_server.py` on the motor Pi.

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
- `KEEP_TRASH_CAN_IN_VIEW`
- `VIEW_EDGE_MARGIN_PX`
- `VIEW_SAFE_STOP_PX`
- `OBSTACLE_HSV_RANGES`
- `AVOID_WHITE_OBSTACLES`
- `OBSTACLE_PATH_CLEARANCE_PX`
- `OBSTACLE_AVOID_OFFSET_PX`
- `OBSTACLE_AVOID_FORWARD_PX`
- `OBSTACLE_AVOID_SIDE_MULTIPLIERS`
- `OBSTACLE_AVOID_BLOCKED_GOAL_PENALTY`
- `RETURN_HOME_WHEN_OBSTACLE_BLOCKED`
- `OBSTACLE_DANGER_DISTANCE_PX`
- `ENABLE_WHITE_BOUNDARY`
- `BOUNDARY_HSV_RANGES`
- `BOUNDARY_CLEARANCE_PX`
- `BOUNDARY_PATH_SAMPLE_STEP_PX`
- `BOUNDARY_START_IGNORE_PX`
- `CAN_FOOTPRINT_SHAPE`
- `CAN_SQUARE_SIDE_SCALE`
- `IGNORE_OBSTACLES_INSIDE_CAN_PX`
- `IGNORE_OBSTACLES_CAN_LENGTH_SCALE`
- `LOCK_MAX_JUMP_PX`

Turn tuning:

- If turns overshoot, lower `TURN_STRENGTH_SCALE` or `MAX_TURN_STRENGTH`.
- If turns are too weak, raise `TURN_STRENGTH_SCALE` or `MIN_TURN_STRENGTH`.

## Notes

- This version is designed for a fixed wall or overhead camera.
- It is much easier to debug than a robot-mounted camera.
- Use strong lighting and bright markers for the first demo.
- The intended robot controller for this project is an ESP32.
