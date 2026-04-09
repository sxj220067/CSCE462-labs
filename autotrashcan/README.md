# AutoTrashCan Vision Prototype

## Overview
This project is a modular, Python-based vision pipeline for a Raspberry Pi trash can that tracks thrown objects and predicts landing points for auto-catching.

### Main goals
- Continuous camera frame acquisition
- Motion-based trash candidate detection
- Object tracking in image space
- 2D trajectory prediction in image space
- Simple left/right/forward command output interface
- Debug display with overlays

## Project structure
- `main.py`: orchestration loop (capture -> detection -> tracking -> prediction -> control)
- `camera.py`: camera capture wrapper (OpenCV VideoCapture)
- `detection.py`: background subtraction + contour filtering
- `tracking.py`: centroid-based tracked path and state machine
- `prediction.py`: velocity estimation + landing point prediction
- `control_interface.py`: action command mapping + motor stub
- `config.py`: all tunable thresholds and runtime flags
- `README.md`: this file

## Requirements
- Python 3.7+
- OpenCV
- NumPy

Install dependencies:

```bash
python3 -m pip install opencv-python numpy
```

## Running

```bash
cd /Users/harp12/autotrashcan
python3 main.py
```

Press `q` or `Esc` to quit.

## Preconfigured behavior
- Uses `config.CAMERA_SOURCE` (`0` default) for USB camera or PiCam.
- `MOTOR_MOCK = True` by default: commands print to console instead of driving motors.
- Debug overlays show bounding boxes, centroid trail, predicted landing point, and FPS.

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
