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
LIGHT_BLUE_TEXT = (255, 220, 120)
YELLOW_TEXT = (0, 255, 255)
WHITE_TEXT = (255, 255, 255)
SAMPLE_TEXT = (255, 255, 255)
SAMPLE_DOT = (255, 0, 255)
WINDOW_NAME = "Version2TrashCan Camera Test"
MAX_CLICK_SAMPLES = 12


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


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


def _suggest_hsv_range(samples):
    if not samples:
        return None
    h_values = [sample["hsv"][0] for sample in samples]
    s_values = [sample["hsv"][1] for sample in samples]
    v_values = [sample["hsv"][2] for sample in samples]
    lower = (
        _clamp(min(h_values) - 8, 0, 179),
        _clamp(min(s_values) - 35, 0, 255),
        _clamp(min(v_values) - 35, 0, 255),
    )
    upper = (
        _clamp(max(h_values) + 8, 0, 179),
        _clamp(max(s_values) + 35, 0, 255),
        _clamp(max(v_values) + 35, 0, 255),
    )
    return lower, upper


def _format_sample(sample):
    if sample is None:
        return "click a marker/object"
    return f"x={sample['point'][0]} y={sample['point'][1]} BGR={sample['bgr']} HSV={sample['hsv']}"


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
        ("light blue back", hsv_values["back"], config.BACK_MARKER_HSV_RANGES, LIGHT_BLUE_TEXT),
        ("yellow target", hsv_values["target"], config.TARGET_HSV_RANGES, YELLOW_TEXT),
    ]
    y = 160
    cv2.putText(frame, "Measured HSV / configured HSV range", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, WHITE_TEXT, 1)
    y += 22
    for label, mean_hsv, ranges, color in rows:
        text = f"{label}: {_format_hsv(mean_hsv)} | range {_format_ranges(ranges)}"
        cv2.putText(frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        y += 22


def _draw_click_samples(frame, samples):
    y = 252
    latest = samples[-1] if samples else None
    cv2.putText(frame, f"Click sample: {_format_sample(latest)}", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, SAMPLE_TEXT, 1)
    y += 20

    suggested = _suggest_hsv_range(samples)
    if suggested is None:
        cv2.putText(frame, "Suggested range: no samples yet", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, SAMPLE_TEXT, 1)
    else:
        lower, upper = suggested
        cv2.putText(frame, f"Suggested range: ({lower}, {upper})", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, SAMPLE_TEXT, 1)
    y += 20

    cv2.putText(frame, "Left-click to sample, c clears samples", (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, SAMPLE_TEXT, 1)
    for sample in samples[-MAX_CLICK_SAMPLES:]:
        x, y_pos = sample["point"]
        cv2.drawMarker(frame, (x, y_pos), SAMPLE_DOT, markerType=cv2.MARKER_CROSS, markerSize=12, thickness=1)


def _sample_patch(frame, hsv_frame, x, y):
    height, width = frame.shape[:2]
    x0 = _clamp(x - 2, 0, width - 1)
    x1 = _clamp(x + 3, 0, width)
    y0 = _clamp(y - 2, 0, height - 1)
    y1 = _clamp(y + 3, 0, height)
    bgr = tuple(int(round(value)) for value in cv2.mean(frame[y0:y1, x0:x1])[:3])
    hsv = tuple(int(round(value)) for value in cv2.mean(hsv_frame[y0:y1, x0:x1])[:3])
    return {"point": (x, y), "bgr": bgr, "hsv": hsv}


def _make_mouse_callback(sample_state):
    def handle_mouse(event, x, y, flags, userdata):
        del flags, userdata
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        frame = sample_state["frame"]
        hsv_frame = sample_state["hsv_frame"]
        if frame is None or hsv_frame is None:
            return
        sample = _sample_patch(frame, hsv_frame, x, y)
        sample_state["samples"].append(sample)
        sample_state["samples"] = sample_state["samples"][-MAX_CLICK_SAMPLES:]
        suggested = _suggest_hsv_range(sample_state["samples"])
        print(f"[CLICK SAMPLE] {_format_sample(sample)}")
        if suggested is not None:
            print(f"[CLICK SAMPLE] suggested HSV range: ({suggested[0]}, {suggested[1]})")

    return handle_mouse


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
    sample_state = {"frame": None, "hsv_frame": None, "samples": []}

    print(
        "Camera detection test starting. "
        "Looking for pink front marker, light blue back marker, and yellow target object."
    )
    print(f"Preview window: {'on' if window_enabled else 'off'}")
    print(f"Camera color mode: {config.CAMERA_COLOR_MODE}")
    if window_enabled:
        cv2.namedWindow(WINDOW_NAME)
        cv2.setMouseCallback(WINDOW_NAME, _make_mouse_callback(sample_state))

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
            sample_state["frame"] = frame
            sample_state["hsv_frame"] = hsv_frame
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
                _draw_click_samples(overlay, sample_state["samples"])
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
                if key == ord("c"):
                    sample_state["samples"].clear()
                    print("Click samples cleared.")

            if args.duration > 0 and now - started_at >= args.duration:
                break

    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        release_capture(cap)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
