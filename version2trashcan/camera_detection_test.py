import argparse
import os
import time

import cv2
import numpy as np

import config
from camera import create_capture, read_frame, release_capture
from controller import compute_command
from detection import create_detector
from main import draw_detection


PINK_TEXT = (203, 192, 255)
ORANGE_TEXT = (0, 140, 255)
YELLOW_TEXT = (0, 255, 255)
WHITE_TEXT = (255, 255, 255)


def _window_available():
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _format_ranges(ranges):
    return " or ".join(f"{lower}-{upper}" for lower, upper in ranges)


def _mean_hsv_for_marker(hsv_frame, marker):
    if marker is None:
        return None
    contour_mask = np.zeros(hsv_frame.shape[:2], dtype=np.uint8)
    cv2.drawContours(contour_mask, [marker["contour"]], -1, 255, thickness=cv2.FILLED)
    mean_hsv = cv2.mean(hsv_frame, mask=contour_mask)[:3]
    return tuple(int(round(value)) for value in mean_hsv)


def _format_hsv(mean_hsv):
    if mean_hsv is None:
        return "missing"
    return f"H={mean_hsv[0]} S={mean_hsv[1]} V={mean_hsv[2]}"


def _format_marker(marker):
    if marker is None:
        return "missing"
    return f"center={marker['center']} area={marker['area']:.0f}"


def _print_status(can_state, target, candidates, telemetry, hsv_values):
    front = can_state["front"] if can_state is not None else None
    back = can_state["back"] if can_state is not None else None
    target_text = _format_marker(target)
    print(
        "[CAMERA TEST] "
        f"robot_found={can_state is not None} "
        f"front={_format_marker(front)} "
        f"front_hsv={_format_hsv(hsv_values['front'])} "
        f"back={_format_marker(back)} "
        f"back_hsv={_format_hsv(hsv_values['back'])} "
        f"object_found={target is not None} "
        f"object={target_text} "
        f"object_hsv={_format_hsv(hsv_values['target'])} "
        f"candidates={len(candidates)} "
        f"distance_px={telemetry['distance_px']} "
        f"angle_deg={telemetry['angle_deg']}"
    )


def _draw_calibration_text(frame, hsv_values):
    rows = [
        ("pink front", hsv_values["front"], config.FRONT_MARKER_HSV_RANGES, PINK_TEXT),
        ("orange back", hsv_values["back"], config.BACK_MARKER_HSV_RANGES, ORANGE_TEXT),
        ("yellow target", hsv_values["target"], config.TARGET_HSV_RANGES, YELLOW_TEXT),
    ]
    y = 160
    cv2.putText(frame, "Measured HSV / configured HSV range", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, WHITE_TEXT, 1)
    y += 22
    for label, mean_hsv, ranges, color in rows:
        text = f"{label}: {_format_hsv(mean_hsv)} | range {_format_ranges(ranges)}"
        cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        y += 22


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test ceiling/wall camera detection for the trash can markers and target object."
    )
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="Print detection status without opening an OpenCV preview window.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Stop after this many seconds. Default 0 runs until q/Esc/Ctrl-C.",
    )
    parser.add_argument(
        "--camera-color-mode",
        choices=("bgr", "rgb_to_bgr"),
        default=None,
        help="Override config.CAMERA_COLOR_MODE for testing swapped red/blue camera channels.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.camera_color_mode is not None:
        config.CAMERA_COLOR_MODE = args.camera_color_mode
    detector = create_detector()
    cap = create_capture()
    window_enabled = config.SHOW_WINDOW and not args.no_window and _window_available()
    started_at = time.time()
    last_status_print = 0.0

    print(
        "Camera detection test starting. "
        "Looking for pink front marker, orange back marker, and yellow target object."
    )
    print(f"Preview window: {'on' if window_enabled else 'off'}")
    print(f"Camera color mode: {config.CAMERA_COLOR_MODE}")

    try:
        while True:
            frame = read_frame(cap)
            if frame is None:
                continue

            result = detector.detect(frame)
            can_state = result["can_state"]
            candidates = result["target_candidates"]
            target = candidates[0] if candidates else None
            command, telemetry = compute_command(can_state, target)
            hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hsv_values = {
                "front": _mean_hsv_for_marker(hsv_frame, can_state["front"] if can_state is not None else None),
                "back": _mean_hsv_for_marker(hsv_frame, can_state["back"] if can_state is not None else None),
                "target": _mean_hsv_for_marker(hsv_frame, target),
            }

            now = time.time()
            if now - last_status_print >= config.STATUS_PRINT_INTERVAL:
                _print_status(can_state, target, candidates, telemetry, hsv_values)
                last_status_print = now

            if window_enabled:
                overlay = frame.copy()
                draw_detection(overlay, can_state, target, command, telemetry)
                _draw_calibration_text(overlay, hsv_values)
                cv2.putText(
                    overlay,
                    "camera test only - no motor commands sent",
                    (10, config.FRAME_HEIGHT - 38),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1,
                )
                cv2.imshow("Version2TrashCan Camera Test", overlay)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    break

            if args.duration > 0 and now - started_at >= args.duration:
                break

    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        release_capture(cap)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
