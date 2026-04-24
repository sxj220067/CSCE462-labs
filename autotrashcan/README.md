# AutoTrashCan Vision Prototype

## Overview
This project is a modular, Python-based vision pipeline for a Raspberry Pi trash can that tracks thrown objects and predicts landing points for auto-catching.

### Main goals
- Continuous camera frame acquisition
- Motion-based trash candidate detection
- Object tracking in image space
- Simple target following in image space
- Simple left/right/forward command output interface
- Debug display with overlays

## Project structure
- `main.py`: orchestration loop (capture -> detection -> tracking -> control)
- `camera.py`: camera capture wrapper (OpenCV VideoCapture)
- `detection.py`: background subtraction + contour filtering
- `tracking.py`: centroid-based tracked path and state machine
- `control_interface.py`: action command mapping + motor stub
- `config.py`: all tunable thresholds and runtime flags
- `README.md`: this file

## Requirements
- Python 3.7+
- OpenCV
- NumPy
- `python3-picamera2` for Raspberry Pi Camera modules on Raspberry Pi OS
- `python3-gpiozero` for L298N motor control on Raspberry Pi OS

Install dependencies in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

On current Raspberry Pi OS releases, installing with `pip` directly into the system Python often fails with `error: externally-managed-environment` (PEP 668). Using a virtual environment avoids that issue cleanly.

If `venv` or `pip` is not available on your Raspberry Pi, install them first:

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv
```

If you prefer to avoid `pip` entirely on Raspberry Pi OS, you can install the main runtime packages from `apt` instead:

```bash
sudo apt install -y python3-opencv python3-numpy
```

If you are using a Raspberry Pi Camera Module connected over CSI, install Picamera2:

```bash
sudo apt install -y python3-picamera2
```

If you are using the included L298N motor driver code, install GPIO Zero:

```bash
sudo apt install -y python3-gpiozero
```

Typical Raspberry Pi OS setup:

```bash
cd ~/projects/CSCE462-labs/autotrashcan
sudo apt update
sudo apt install -y python3-venv python3-opencv python3-numpy python3-picamera2 python3-gpiozero
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

If `opencv-python` still fails to install inside the virtual environment, keep using the `apt`-installed `python3-opencv` and `python3-numpy` packages outside the venv instead of forcing `pip` with `--break-system-packages`.

## Running

```bash
cd ~/projects/CSCE462-labs/autotrashcan
source .venv/bin/activate
python3 main.py
```

Press `q` or `Esc` to quit.

To view the live camera feed without detection or motor control:

```bash
cd ~/projects/CSCE462-labs/autotrashcan
source .venv/bin/activate
python3 camera_view.py
```

This opens a simple preview window with a center crosshair, center capture circle, and FPS.

Current camera tuning is set up for an OV5647-style 5MP module:
- capture stream: `1920x1080`
- processing stream: `960x540`

This keeps the preview sharp while avoiding a large FPS hit in the vision pipeline.
The preview window also applies optional display-only sharpening, which can make edges easier to inspect but will not fix a physically out-of-focus lens.

## Preconfigured behavior
- `CAMERA_BACKEND = "auto"` tries `Picamera2` first, then falls back to OpenCV.
- Use `CAMERA_BACKEND = "picamera2"` for Raspberry Pi Camera modules.
- Use `CAMERA_BACKEND = "opencv"` with `CAMERA_SOURCE = 0` for USB webcams.
- `MOTOR_MOCK = False` with the current defaults, so the code will drive an L298N-connected motor.
- Debug overlays show bounding boxes, centroid trail, predicted landing point, and FPS.

## L298N Hardware Wiring
Default Raspberry Pi GPIO assignments in `config.py` for a two-motor differential drive:

- `GPIO18` -> `ENA` on the L298N
- `GPIO23` -> `IN1` on the L298N
- `GPIO24` -> `IN2` on the L298N
- `GPIO13` -> `ENB` on the L298N
- `GPIO5` -> `IN3` on the L298N
- `GPIO6` -> `IN4` on the L298N
- Raspberry Pi `GND` -> L298N `GND`
- Left motor leads -> L298N `OUT1` and `OUT2`
- Right motor leads -> L298N `OUT3` and `OUT4`
- External motor power supply -> L298N `12V`/`VIN` and `GND`

Important hardware notes:

- Do not power the motors directly from Raspberry Pi GPIO pins.
- Share ground between the Raspberry Pi and the L298N.
- Keep the `ENA` and `ENB` jumpers off if you want PWM speed control from the Raspberry Pi.
- If one side runs backward when it should go forward, flip that motor's leads or set `LEFT_MOTOR_INVERTED` / `RIGHT_MOTOR_INVERTED` in `config.py`.

Current motion mapping with two motors:

- `MOVE_LEFT`: pivot left by reversing the left motor and driving the right motor forward
- `MOVE_RIGHT`: pivot right by driving the left motor forward and reversing the right motor
- `MOVE_FORWARD`: both motors forward at cruising duty cycle
- `MOVE_REVERSE`: both motors backward at the reverse duty cycle
- `STOP`: both motors off

## Keys
- `q`: Quit
- `Esc`: Quit

## Tuning parameters (first priority)
1. `config.MIN_CONTOUR_AREA` and `config.MAX_CONTOUR_AREA` to match object sizes
2. `config.MOG_VAR_THRESHOLD` and `config.THRESHOLD_VALUE` for sensitivity to motion
3. `config.GROUND_LINE_RATIO` for landing plane in image coordinates
4. `config.GRAVITY_PX_PER_S2` to match approximate image-space fall speed
5. `config.CENTER_DEADZONE_PX` for command hysteresis

## Future upgrades
- Replace detector with YOLO/SSD trash object detection
- Add camera calibration + lens distortion correction
- Use 3D triangulation from stereo camera setup
- Use Kalman filter for smoother tracking and state estimation
- Add serial / ROS communication to motor controller (PWM driver)
- Add threshold adaptation and scene autoregistration

## Notes
- Keep CPU usage low: run at reduced resolution if needed (e.g., 320x240 in `config`).
- This prototype assumes one main moving object and may be confused by multiple simultaneous motions.
- The predicted landing `x` is in image coordinates and mapped to left/right only.
