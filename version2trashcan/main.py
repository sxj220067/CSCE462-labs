import os
import time

import cv2

import config
from camera import create_capture, read_frame, release_capture
from controller import compute_command
from detection import create_detector
from transport import create_transport


def draw_detection(
    frame,
    can_state,
    target,
    command,
    telemetry,
    home_center=None,
    returning_home=False,
    target_collected=False,
    view_safety=False,
    obstacles=None,
    avoidance_target=None,
    boundaries=None,
    boundary_safety=False,
):
    del home_center, returning_home, target_collected, view_safety
    del obstacles, avoidance_target, boundaries, boundary_safety

    if can_state is not None:
        front = can_state["front"]["center"]
        back = can_state["back"]["center"]
        center = can_state["center"]
        cv2.circle(frame, front, 8, (203, 192, 255), -1)
        cv2.circle(frame, back, 8, (0, 255, 0), -1)
        cv2.circle(frame, center, 6, (255, 255, 255), -1)
        cv2.line(frame, back, front, (255, 255, 255), 2)
        cv2.putText(frame, "front", (front[0] + 8, front[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (203, 192, 255), 2)
        cv2.putText(frame, "back", (back[0] + 8, back[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    else:
        cv2.putText(frame, "Trash can markers not found", (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    if target is not None:
        x, y, w, h = target["bbox"]
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
        cv2.circle(frame, target["center"], 5, (0, 255, 255), -1)
        cv2.putText(frame, "target", (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    else:
        cv2.putText(frame, "Target not found", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

    if can_state is not None and target is not None:
        cv2.line(frame, can_state["center"], target["center"], (0, 255, 255), 2)

    dist_px = telemetry["distance_px"]
    angle_deg = telemetry["angle_deg"]
    cv2.putText(frame, f"Command: {command}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
    cv2.putText(frame, f"Distance px: {dist_px if dist_px is not None else 'n/a'}", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
    cv2.putText(frame, f"Angle deg: {angle_deg if angle_deg is not None else 'n/a'}", (10, 135), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
    cv2.putText(frame, "q/Esc quit", (10, config.FRAME_HEIGHT - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)


def main():
    detector = create_detector()
    cap = create_capture()
    transport = create_transport()
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    window_enabled = config.SHOW_WINDOW and has_display
    last_status_print = 0.0
    last_command_sent_at = 0.0
    last_command = None

    print(
        f"Version2TrashCan starting: backend={config.CAMERA_BACKEND}, "
        f"transport={config.COMMAND_TRANSPORT}, window={'on' if window_enabled else 'off'}"
    )

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
            if command != last_command or (now - last_command_sent_at) >= config.COMMAND_UPDATE_INTERVAL_S:
                transport.send(command, telemetry)
                last_command = command
                last_command_sent_at = now

            if now - last_status_print >= config.STATUS_PRINT_INTERVAL:
                print(
                    "[STATUS] "
                    f"can_found={can_state is not None} "
                    f"target_found={target is not None} "
                    f"candidates={len(candidates)} "
                    f"command={command} "
                    f"distance={telemetry['distance_px']} "
                    f"angle={telemetry['angle_deg']} "
                    f"turn={telemetry['turn_strength']}"
                )
                last_status_print = now

            if window_enabled:
                overlay = frame.copy()
                draw_detection(overlay, can_state, target, command, telemetry)
                cv2.imshow(config.WINDOW_NAME, overlay)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    break

    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        transport.send(config.CMD_STOP)
        transport.close()
        release_capture(cap)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
