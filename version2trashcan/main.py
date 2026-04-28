import os
import math
import time

import cv2

import config
from camera import create_capture, read_frame, release_capture
from controller import clamp, compute_command, signed_angle_deg
from detection import create_detector
from transport import create_transport


def screen_center():
    return (int(config.FRAME_WIDTH / 2), int(config.FRAME_HEIGHT / 2))


def target_inside_trash_can(can_state, target):
    if can_state is None or target is None:
        return False

    dx = target["center"][0] - can_state["center"][0]
    dy = target["center"][1] - can_state["center"][1]
    return math.hypot(dx, dy) <= config.TARGET_COLLECTED_DISTANCE_PX


def compute_heading_command(can_state, point):
    if can_state is None:
        return config.CMD_STOP, {"distance_px": None, "angle_deg": None, "turn_strength": 0}

    center = can_state["center"]
    target_vector = (point[0] - center[0], point[1] - center[1])
    angle_deg = signed_angle_deg(can_state["heading"], target_vector)
    if abs(angle_deg) <= config.HEADING_ALIGNMENT_DEG:
        return config.CMD_STOP, {"distance_px": 0.0, "angle_deg": angle_deg, "turn_strength": 0}

    turn_ratio = min(1.0, abs(angle_deg) / config.FULL_TURN_ANGLE_DEG)
    turn_strength = int(round(turn_ratio * 100 * config.TURN_STRENGTH_SCALE))
    turn_strength = clamp(turn_strength, config.MIN_TURN_STRENGTH, config.MAX_TURN_STRENGTH)
    command = config.CMD_LEFT if angle_deg < 0.0 else config.CMD_RIGHT
    return command, {"distance_px": 0.0, "angle_deg": angle_deg, "turn_strength": turn_strength}


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
    del target_collected, view_safety
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
    elif can_state is not None and returning_home and home_center is not None:
        cv2.line(frame, can_state["center"], home_center, (255, 255, 0), 2)
    elif can_state is not None and home_center is not None:
        cv2.line(frame, can_state["center"], screen_center(), (255, 255, 0), 1)

    if home_center is not None:
        cv2.drawMarker(frame, home_center, (255, 255, 0), markerType=cv2.MARKER_TILTED_CROSS, markerSize=18, thickness=2)
        cv2.putText(frame, "home", (home_center[0] + 8, home_center[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

    dist_px = telemetry["distance_px"]
    angle_deg = telemetry["angle_deg"]
    cv2.putText(frame, f"Command: {command}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
    cv2.putText(frame, f"Distance px: {dist_px if dist_px is not None else 'n/a'}", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
    cv2.putText(frame, f"Angle deg: {angle_deg if angle_deg is not None else 'n/a'}", (10, 135), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
    cv2.putText(frame, "q/Esc quit, h set home", (10, config.FRAME_HEIGHT - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)


def main():
    detector = create_detector()
    cap = create_capture()
    transport = create_transport()
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    window_enabled = config.SHOW_WINDOW and has_display
    last_status_print = 0.0
    last_command_sent_at = 0.0
    last_command = None
    home_center = None
    target_lost_since = None
    target_inside_since = None
    return_home_mode = False
    align_home_mode = False

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
            now = time.time()

            if home_center is None and can_state is not None:
                home_center = can_state["center"]
                print(f"Home position set to {home_center}")

            if target is not None:
                target_lost_since = None
                align_home_mode = False
                if target_inside_trash_can(can_state, target):
                    if target_inside_since is None:
                        target_inside_since = now
                    elif now - target_inside_since >= config.TARGET_COLLECTED_SECONDS:
                        return_home_mode = config.RETURN_HOME_WHEN_TARGET_COLLECTED
                        print("Target inside trash can for 2.0s. Returning home.")
                else:
                    target_inside_since = None
            else:
                target_inside_since = None
                if target_lost_since is None:
                    target_lost_since = now
                elif now - target_lost_since >= config.TARGET_LOST_RETURN_HOME_SECONDS:
                    return_home_mode = True

            if return_home_mode and home_center is not None:
                command_target = {"center": home_center}
                returning_home = True
                stop_distance_px = config.HOME_STOP_PX
            elif align_home_mode:
                command_target = None
                returning_home = False
                stop_distance_px = None
            elif target is not None:
                command_target = target
                returning_home = False
                stop_distance_px = None
            else:
                command_target = None
                returning_home = False
                stop_distance_px = None

            if align_home_mode:
                command, telemetry = compute_heading_command(can_state, screen_center())
                if command == config.CMD_STOP:
                    align_home_mode = False
                    print("Facing center. Stopping.")
            else:
                command, telemetry = compute_command(can_state, command_target, stop_distance_px)

            if returning_home and command == config.CMD_STOP:
                return_home_mode = False
                target_lost_since = None
                target_inside_since = None
                align_home_mode = True
                print("Arrived home. Facing center.")

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
                    f"returning_home={returning_home} "
                    f"aligning_home={align_home_mode} "
                    f"command={command} "
                    f"distance={telemetry['distance_px']} "
                    f"angle={telemetry['angle_deg']} "
                    f"turn={telemetry['turn_strength']}"
                )
                last_status_print = now

            if window_enabled:
                overlay = frame.copy()
                draw_detection(overlay, can_state, target, command, telemetry, home_center, returning_home)
                cv2.imshow(config.WINDOW_NAME, overlay)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    break
                if key == ord("h") and can_state is not None:
                    home_center = can_state["center"]
                    return_home_mode = False
                    align_home_mode = False
                    target_lost_since = None
                    target_inside_since = None
                    print(f"Home position reset to {home_center}")

    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        transport.send(config.CMD_STOP)
        transport.close()
        release_capture(cap)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
