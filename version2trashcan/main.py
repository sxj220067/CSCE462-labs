import os
import math
import time

import cv2

import config
from camera import create_capture, read_frame, release_capture
from controller import choose_target, compute_command
from detection import create_detector
from transport import create_transport


def clamp_point(point):
    return (
        max(0, min(config.FRAME_WIDTH - 1, int(point[0]))),
        max(0, min(config.FRAME_HEIGHT - 1, int(point[1]))),
    )


def obstacle_blocks_path(start, goal, obstacle):
    sx, sy = start
    gx, gy = goal
    ox, oy = obstacle["center"]
    dx = gx - sx
    dy = gy - sy
    length_sq = (dx * dx) + (dy * dy)
    if length_sq <= 1:
        return False

    projection = (((ox - sx) * dx) + ((oy - sy) * dy)) / length_sq
    if projection <= 0.0 or projection >= 1.0:
        return False

    closest_x = sx + (projection * dx)
    closest_y = sy + (projection * dy)
    distance_to_path = math.hypot(ox - closest_x, oy - closest_y)
    return distance_to_path <= obstacle["radius"] + config.OBSTACLE_PATH_CLEARANCE_PX


def choose_avoidance_target(can_state, command_target, obstacles):
    if not config.AVOID_WHITE_OBSTACLES or can_state is None or command_target is None:
        return None

    start = can_state["center"]
    goal = command_target["center"]
    blocking = [obstacle for obstacle in obstacles if obstacle_blocks_path(start, goal, obstacle)]
    if not blocking:
        return None

    obstacle = min(blocking, key=lambda item: math.hypot(item["center"][0] - start[0], item["center"][1] - start[1]))
    sx, sy = start
    gx, gy = goal
    dx = gx - sx
    dy = gy - sy
    path_length = max(1.0, math.hypot(dx, dy))
    perp_x = -dy / path_length
    perp_y = dx / path_length

    center_x = config.FRAME_WIDTH / 2
    center_y = config.FRAME_HEIGHT / 2
    ox, oy = obstacle["center"]
    option_a = (ox + (perp_x * config.OBSTACLE_AVOID_OFFSET_PX), oy + (perp_y * config.OBSTACLE_AVOID_OFFSET_PX))
    option_b = (ox - (perp_x * config.OBSTACLE_AVOID_OFFSET_PX), oy - (perp_y * config.OBSTACLE_AVOID_OFFSET_PX))
    dist_a = math.hypot(option_a[0] - center_x, option_a[1] - center_y)
    dist_b = math.hypot(option_b[0] - center_x, option_b[1] - center_y)
    avoid_center = option_a if dist_a < dist_b else option_b
    return {"center": clamp_point(avoid_center), "obstacle": obstacle}


def filter_obstacles_inside_can(can_state, obstacles):
    if can_state is None:
        return obstacles
    can_x, can_y = can_state["center"]
    filtered = []
    for obstacle in obstacles:
        dx = obstacle["center"][0] - can_x
        dy = obstacle["center"][1] - can_y
        if math.hypot(dx, dy) > config.IGNORE_OBSTACLES_INSIDE_CAN_PX:
            filtered.append(obstacle)
    return filtered


def draw_detection(frame, can_state, target, command, telemetry, home_center=None, returning_home=False, target_collected=False, view_safety=False, obstacles=None, avoidance_target=None):
    obstacles = [] if obstacles is None else obstacles
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

    for obstacle in obstacles:
        x, y, w, h = obstacle["bbox"]
        cv2.rectangle(frame, (x, y), (x + w, y + h), (245, 245, 245), 2)
        cv2.circle(frame, obstacle["center"], 4, (245, 245, 245), -1)

    if avoidance_target is not None:
        avoid_center = avoidance_target["center"]
        cv2.drawMarker(frame, avoid_center, (0, 165, 255), markerType=cv2.MARKER_CROSS, markerSize=18, thickness=2)
        cv2.putText(frame, "avoid", (avoid_center[0] + 8, avoid_center[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)

    if home_center is not None:
        cv2.drawMarker(frame, home_center, (255, 255, 0), markerType=cv2.MARKER_TILTED_CROSS, markerSize=18, thickness=2)
        cv2.putText(frame, "home", (home_center[0] + 8, home_center[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

    if config.KEEP_TRASH_CAN_IN_VIEW:
        margin = config.VIEW_EDGE_MARGIN_PX
        cv2.rectangle(frame, (margin, margin), (config.FRAME_WIDTH - margin, config.FRAME_HEIGHT - margin), (180, 180, 180), 1)
        if view_safety:
            cv2.putText(frame, "view safety", (10, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 165, 255), 2)

    if can_state is not None and target is not None:
        cv2.line(frame, can_state["center"], target["center"], (0, 255, 255), 2)
    elif can_state is not None and returning_home and home_center is not None:
        cv2.line(frame, can_state["center"], home_center, (255, 255, 0), 2)
    if can_state is not None and avoidance_target is not None:
        cv2.line(frame, can_state["center"], avoidance_target["center"], (0, 165, 255), 2)

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
            obstacles = filter_obstacles_inside_can(can_state, result["obstacle_candidates"])
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
            view_safety = False
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

            if config.KEEP_TRASH_CAN_IN_VIEW and can_state is not None:
                can_x, can_y = can_state["center"]
                margin = config.VIEW_EDGE_MARGIN_PX
                near_edge = (
                    can_x <= margin
                    or can_x >= config.FRAME_WIDTH - margin
                    or can_y <= margin
                    or can_y >= config.FRAME_HEIGHT - margin
                )
                if near_edge:
                    command_target = {"center": (int(config.FRAME_WIDTH / 2), int(config.FRAME_HEIGHT / 2))}
                    returning_home = False
                    view_safety = True

            avoidance_target = None
            if not view_safety:
                avoidance_target = choose_avoidance_target(can_state, command_target, obstacles)
                if avoidance_target is not None:
                    command_target = {"center": avoidance_target["center"]}
                    returning_home = False

            stop_distance_px = config.VIEW_SAFE_STOP_PX if view_safety else config.HOME_STOP_PX if returning_home else None
            raw_command, telemetry = compute_command(can_state, command_target, stop_distance_px)
            if returning_home and raw_command == config.CMD_STOP:
                target_collected = False
                return_home_mode = False
                target_seen_once = False
                target_inside_since = None
                locked_target = None
                missed_target_frames = 0
                returning_home = False
                command_target = None
                print("Arrived home. Mission state reset.")
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
                    f"missed={missed_target_frames} collected={target_collected} return_mode={return_home_mode} returning_home={returning_home} view_safety={view_safety} obstacles={len(obstacles)} avoiding={avoidance_target is not None} "
                    f"command={command} raw={raw_command} "
                    f"distance={telemetry['distance_px']} angle={telemetry['angle_deg']} "
                    f"turn={telemetry['turn_strength']}"
                )
                last_status_print = now

            if window_enabled:
                overlay = frame.copy()
                draw_detection(overlay, can_state, target, command, telemetry, home_center, returning_home, target_collected, view_safety, obstacles, avoidance_target)
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
