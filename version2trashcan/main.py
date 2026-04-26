import os
import time

import cv2

import config
from camera import create_capture, read_frame, release_capture
from controller import choose_target, compute_command
from detection import create_detector
from transport import create_transport


def draw_detection(frame, can_state, target, command, telemetry, home_center=None, returning_home=False, target_collected=False):
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
        target_label = "collected" if target_collected else "target"
        cv2.putText(frame, target_label, (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    else:
        cv2.putText(frame, "Target not found", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

    if home_center is not None:
        cv2.drawMarker(frame, home_center, (255, 255, 0), markerType=cv2.MARKER_TILTED_CROSS, markerSize=18, thickness=2)
        cv2.putText(frame, "home", (home_center[0] + 8, home_center[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

    if can_state is not None and target is not None:
        cv2.line(frame, can_state["center"], target["center"], (0, 255, 255), 2)
    elif can_state is not None and returning_home and home_center is not None:
        cv2.line(frame, can_state["center"], home_center, (255, 255, 0), 2)

    dist_px = telemetry["distance_px"]
    angle_deg = telemetry["angle_deg"]
    cv2.putText(frame, f"Command: {command}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
    cv2.putText(frame, f"Distance px: {dist_px if dist_px is not None else 'n/a'}", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
    cv2.putText(frame, f"Angle deg: {angle_deg if angle_deg is not None else 'n/a'}", (10, 135), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
    cv2.putText(frame, f"Collected: {target_collected}", (10, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
    cv2.putText(frame, "q/Esc quit, r reset target, h set home", (10, config.FRAME_HEIGHT - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)


def main():
    cap = create_capture()
    detector = create_detector()
    transport = create_transport()
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    window_enabled = config.SHOW_WINDOW and has_display
    last_status_print = 0.0
    last_command_sent_at = 0.0
    last_command = config.CMD_STOP
    pending_command = None
    pending_command_count = 0
    locked_target = None
    missed_target_frames = 0
    home_center = None
    target_inside_since = None
    target_collected = False
    return_home_mode = False
    target_seen_once = False

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
            candidate_targets = result["target_candidates"]
            if home_center is None and can_state is not None:
                home_center = can_state["center"]
                print(f"Home position set to {home_center}")

            if return_home_mode:
                target = None
                locked_target = None
            else:
                target = choose_target(candidate_targets, locked_target)
                if target is not None:
                    target_seen_once = True
                    locked_target = target
                    missed_target_frames = 0
                elif locked_target is not None and missed_target_frames < config.LOCK_MAX_MISSED_FRAMES:
                    target = locked_target
                    missed_target_frames += 1
                else:
                    locked_target = None
                    target = None
                    if config.RETURN_HOME_WHEN_TARGET_LOST and target_seen_once:
                        return_home_mode = True
                        print("Target lost. Returning home.")
                    missed_target_frames = 0

            now = time.time()
            target_inside = False
            if can_state is not None and target is not None:
                dx = target["center"][0] - can_state["center"][0]
                dy = target["center"][1] - can_state["center"][1]
                target_inside = ((dx * dx) + (dy * dy)) ** 0.5 <= config.TARGET_COLLECTED_DISTANCE_PX

            if not target_collected:
                if target_inside:
                    if target_inside_since is None:
                        target_inside_since = now
                    elif now - target_inside_since >= config.TARGET_COLLECTED_SECONDS:
                        target_collected = True
                        return_home_mode = config.RETURN_HOME_WHEN_TARGET_COLLECTED
                        locked_target = None
                        print("Target collected. Returning home.")
                else:
                    target_inside_since = None

            returning_home = False
            command_target = target
            if return_home_mode:
                command_target = None
            if (
                command_target is None
                and return_home_mode
                and home_center is not None
                and can_state is not None
            ):
                command_target = {"center": home_center}
                returning_home = True

            stop_distance_px = config.HOME_STOP_PX if returning_home else None
            raw_command, telemetry = compute_command(can_state, command_target, stop_distance_px)
            if raw_command == last_command:
                command = raw_command
                pending_command = None
                pending_command_count = 0
            else:
                if raw_command == pending_command:
                    pending_command_count += 1
                else:
                    pending_command = raw_command
                    pending_command_count = 1

                if raw_command in {config.CMD_FORWARD, config.CMD_STOP}:
                    command = raw_command
                elif pending_command_count >= config.COMMAND_CHANGE_CONFIRMATIONS:
                    command = raw_command
                else:
                    command = last_command

            if command != last_command or (now - last_command_sent_at) >= config.COMMAND_UPDATE_INTERVAL_S:
                transport.send(command, telemetry)
                last_command = command
                last_command_sent_at = now

            if now - last_status_print >= config.STATUS_PRINT_INTERVAL:
                print(
                    f"[STATUS] can_found={can_state is not None} "
                    f"target_found={target is not None} candidates={len(candidate_targets)} "
                    f"missed={missed_target_frames} collected={target_collected} return_mode={return_home_mode} returning_home={returning_home} "
                    f"command={command} raw={raw_command} "
                    f"distance={telemetry['distance_px']} angle={telemetry['angle_deg']} "
                    f"turn={telemetry['turn_strength']}"
                )
                last_status_print = now

            if window_enabled:
                overlay = frame.copy()
                draw_detection(overlay, can_state, target, command, telemetry, home_center, returning_home, target_collected)
                cv2.imshow(config.WINDOW_NAME, overlay)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    break
                if key == ord("r"):
                    locked_target = None
                    missed_target_frames = 0
                    target_inside_since = None
                    target_collected = False
                    return_home_mode = False
                    target_seen_once = False
                    print("Target lock reset.")
                if key == ord("h") and can_state is not None:
                    home_center = can_state["center"]
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
