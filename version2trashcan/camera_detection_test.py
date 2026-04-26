import argparse
import os
import time

import cv2

import config
from camera import create_capture, read_frame, release_capture
from controller import compute_command
from detection import create_detector
from main import draw_detection


def _window_available():
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _format_marker(marker):
    if marker is None:
        return "missing"
    return f"center={marker['center']} area={marker['area']:.0f}"


def _print_status(can_state, target, candidates, telemetry):
    front = can_state["front"] if can_state is not None else None
    back = can_state["back"] if can_state is not None else None
    target_text = _format_marker(target)
    print(
        "[CAMERA TEST] "
        f"robot_found={can_state is not None} "
        f"front={_format_marker(front)} "
        f"back={_format_marker(back)} "
        f"object_found={target is not None} "
        f"object={target_text} "
        f"candidates={len(candidates)} "
        f"distance_px={telemetry['distance_px']} "
        f"angle_deg={telemetry['angle_deg']}"
    )


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
    return parser.parse_args()


def main():
    args = parse_args()
    detector = create_detector()
    cap = create_capture()
    window_enabled = config.SHOW_WINDOW and not args.no_window and _window_available()
    started_at = time.time()
    last_status_print = 0.0

    print(
        "Camera detection test starting. "
        "Looking for pink front marker, green back marker, and yellow target object."
    )
    print(f"Preview window: {'on' if window_enabled else 'off'}")

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

            now = time.time()
            if now - last_status_print >= config.STATUS_PRINT_INTERVAL:
                _print_status(can_state, target, candidates, telemetry)
                last_status_print = now

            if window_enabled:
                overlay = frame.copy()
                draw_detection(overlay, can_state, target, command, telemetry)
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
