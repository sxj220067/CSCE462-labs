import os
import math
import time

import cv2
import numpy as np

import config
from camera import create_capture, read_frame, release_capture
from controller import compute_command
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


def path_crosses_boundary(start, goal, boundary_mask):
    if boundary_mask is None:
        return False

    sx, sy = start
    gx, gy = goal
    dx = gx - sx
    dy = gy - sy
    path_length = math.hypot(dx, dy)
    if path_length <= 1.0:
        return False

    sample_count = max(1, int(path_length / config.BOUNDARY_PATH_SAMPLE_STEP_PX))
    radius = max(0, int(config.BOUNDARY_CLEARANCE_PX))
    height, width = boundary_mask.shape[:2]

    for index in range(1, sample_count + 1):
        ratio = index / sample_count
        if path_length * ratio < config.BOUNDARY_START_IGNORE_PX:
            continue
        x = int(round(sx + (dx * ratio)))
        y = int(round(sy + (dy * ratio)))
        x0 = max(0, x - radius)
        x1 = min(width, x + radius + 1)
        y0 = max(0, y - radius)
        y1 = min(height, y + radius + 1)
        if np.any(boundary_mask[y0:y1, x0:x1] > 0):
            return True
    return False


def square_can_footprint(can_state):
    if can_state is None:
        return None

    can_x, can_y = can_state["center"]
    front_x, front_y = can_state["front"]["center"]
    back_x, back_y = can_state["back"]["center"]
    heading_x = front_x - back_x
    heading_y = front_y - back_y
    marker_distance = math.hypot(heading_x, heading_y)
    if marker_distance <= 1.0:
        return None

    half_side = max(
        config.IGNORE_OBSTACLES_INSIDE_CAN_PX,
        marker_distance * config.CAN_SQUARE_SIDE_SCALE,
    ) / 2.0
    unit_x = heading_x / marker_distance
    unit_y = heading_y / marker_distance
    perp_x = -unit_y
    perp_y = unit_x

    corners = [
        (can_x + (unit_x * half_side) + (perp_x * half_side), can_y + (unit_y * half_side) + (perp_y * half_side)),
        (can_x + (unit_x * half_side) - (perp_x * half_side), can_y + (unit_y * half_side) - (perp_y * half_side)),
        (can_x - (unit_x * half_side) - (perp_x * half_side), can_y - (unit_y * half_side) - (perp_y * half_side)),
        (can_x - (unit_x * half_side) + (perp_x * half_side), can_y - (unit_y * half_side) + (perp_y * half_side)),
    ]
    return {
        "center": can_state["center"],
        "heading_unit": (unit_x, unit_y),
        "perp_unit": (perp_x, perp_y),
        "half_side": half_side,
        "corners": [clamp_point(corner) for corner in corners],
    }


def point_inside_square_can(point, footprint):
    point_x, point_y = point
    center_x, center_y = footprint["center"]
    dx = point_x - center_x
    dy = point_y - center_y
    unit_x, unit_y = footprint["heading_unit"]
    perp_x, perp_y = footprint["perp_unit"]
    forward_distance = abs((dx * unit_x) + (dy * unit_y))
    side_distance = abs((dx * perp_x) + (dy * perp_y))
    return forward_distance <= footprint["half_side"] and side_distance <= footprint["half_side"]


def can_view_safety_points(can_state):
    if can_state is None:
        return []

    points = [
        can_state["center"],
        can_state["front"]["center"],
        can_state["back"]["center"],
    ]
    if config.CAN_FOOTPRINT_SHAPE == "square":
        footprint = square_can_footprint(can_state)
        if footprint is not None:
            points.extend(footprint["corners"])
    return points


def can_near_camera_edge(can_state):
    margin = config.VIEW_EDGE_MARGIN_PX
    for point_x, point_y in can_view_safety_points(can_state):
        if (
            point_x <= margin
            or point_x >= config.FRAME_WIDTH - margin
            or point_y <= margin
            or point_y >= config.FRAME_HEIGHT - margin
        ):
            return True
    return False


def point_inside_safe_view(point):
    margin = config.VIEW_EDGE_MARGIN_PX if config.KEEP_TRASH_CAN_IN_VIEW else 0
    point_x, point_y = point
    return (
        margin < point_x < config.FRAME_WIDTH - margin
        and margin < point_y < config.FRAME_HEIGHT - margin
    )


def path_blocked_by_obstacles(start, goal, obstacles):
    return any(obstacle_blocks_path(start, goal, obstacle) for obstacle in obstacles)


def heading_turn_cost(can_state, candidate):
    heading_x, heading_y = can_state["heading"]
    target_x = candidate[0] - can_state["center"][0]
    target_y = candidate[1] - can_state["center"][1]
    heading_length = math.hypot(heading_x, heading_y)
    target_length = math.hypot(target_x, target_y)
    if heading_length <= 1.0 or target_length <= 1.0:
        return 0.0

    heading_angle = math.atan2(heading_y, heading_x)
    target_angle = math.atan2(target_y, target_x)
    angle = abs(math.degrees(target_angle - heading_angle))
    while angle > 180.0:
        angle = abs(angle - 360.0)
    return angle


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
    unit_x = dx / path_length
    unit_y = dy / path_length
    perp_x = -unit_y
    perp_y = unit_x

    ox, oy = obstacle["center"]
    obstacle_clearance = obstacle["radius"] + config.OBSTACLE_PATH_CLEARANCE_PX
    forward_offsets = (
        0.0,
        config.OBSTACLE_AVOID_FORWARD_PX,
        -config.OBSTACLE_AVOID_FORWARD_PX * 0.5,
    )

    best_candidate = None
    best_score = None
    for side in (-1.0, 1.0):
        for side_multiplier in config.OBSTACLE_AVOID_SIDE_MULTIPLIERS:
            side_offset = max(config.OBSTACLE_AVOID_OFFSET_PX, obstacle_clearance * side_multiplier)
            for forward_offset in forward_offsets:
                candidate = (
                    ox + (unit_x * forward_offset) + (perp_x * side * side_offset),
                    oy + (unit_y * forward_offset) + (perp_y * side * side_offset),
                )
                candidate = clamp_point(candidate)
                if not point_inside_safe_view(candidate):
                    continue
                if path_blocked_by_obstacles(start, candidate, obstacles):
                    continue

                goal_blocked = path_blocked_by_obstacles(candidate, goal, obstacles)
                score = math.hypot(candidate[0] - sx, candidate[1] - sy)
                score += math.hypot(gx - candidate[0], gy - candidate[1])
                score += heading_turn_cost(can_state, candidate) * 2.0
                if goal_blocked:
                    score += config.OBSTACLE_AVOID_BLOCKED_GOAL_PENALTY

                if best_score is None or score < best_score:
                    best_score = score
                    best_candidate = {
                        "center": candidate,
                        "obstacle": obstacle,
                        "predicted_goal_blocked": goal_blocked,
                    }

    if best_candidate is not None:
        return best_candidate

    return {"center": None, "obstacle": obstacle, "no_path": True}


def filter_obstacles_inside_can(can_state, obstacles):
    if can_state is None:
        return obstacles

    if config.CAN_FOOTPRINT_SHAPE == "square":
        footprint = square_can_footprint(can_state)
        if footprint is not None:
            return [obstacle for obstacle in obstacles if not point_inside_square_can(obstacle["center"], footprint)]

    can_x, can_y = can_state["center"]
    front_x, front_y = can_state["front"]["center"]
    back_x, back_y = can_state["back"]["center"]
    marker_distance = math.hypot(front_x - back_x, front_y - back_y)
    ignore_radius = max(
        config.IGNORE_OBSTACLES_INSIDE_CAN_PX,
        marker_distance * config.IGNORE_OBSTACLES_CAN_LENGTH_SCALE,
    )
    filtered = []
    for obstacle in obstacles:
        dx = obstacle["center"][0] - can_x
        dy = obstacle["center"][1] - can_y
        if math.hypot(dx, dy) > ignore_radius:
            filtered.append(obstacle)
    return filtered


def closest_obstacle_distance(can_state, obstacles):
    if can_state is None or not obstacles:
        return None
    can_x, can_y = can_state["center"]
    return min(math.hypot(obstacle["center"][0] - can_x, obstacle["center"][1] - can_y) for obstacle in obstacles)


def draw_detection(frame, can_state, target, command, telemetry, home_center=None, returning_home=False, target_collected=False, view_safety=False, obstacles=None, avoidance_target=None, boundaries=None, boundary_safety=False):
    obstacles = [] if obstacles is None else obstacles
    boundaries = [] if boundaries is None else boundaries
    if can_state is not None:
        front = can_state["front"]["center"]
        back = can_state["back"]["center"]
        center = can_state["center"]
        footprint = square_can_footprint(can_state) if config.CAN_FOOTPRINT_SHAPE == "square" else None
        if footprint is not None:
            points = np.array(footprint["corners"], dtype=np.int32)
            cv2.polylines(frame, [points], True, (255, 255, 255), 1)
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

    for boundary in boundaries:
        x, y, w, h = boundary["bbox"]
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 255), 2)
        cv2.putText(frame, "boundary", (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)

    if avoidance_target is not None:
        avoid_center = avoidance_target["center"]
        if avoid_center is not None:
            cv2.drawMarker(frame, avoid_center, (0, 165, 255), markerType=cv2.MARKER_CROSS, markerSize=18, thickness=2)
            cv2.putText(frame, "avoid", (avoid_center[0] + 8, avoid_center[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)
        else:
            obstacle_center = avoidance_target["obstacle"]["center"]
            cv2.putText(frame, "no obstacle path", (obstacle_center[0] + 8, obstacle_center[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)

    if home_center is not None:
        cv2.drawMarker(frame, home_center, (255, 255, 0), markerType=cv2.MARKER_TILTED_CROSS, markerSize=18, thickness=2)
        cv2.putText(frame, "home", (home_center[0] + 8, home_center[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

    if config.KEEP_TRASH_CAN_IN_VIEW:
        margin = config.VIEW_EDGE_MARGIN_PX
        cv2.rectangle(frame, (margin, margin), (config.FRAME_WIDTH - margin, config.FRAME_HEIGHT - margin), (180, 180, 180), 1)
        if view_safety:
            cv2.putText(frame, "view safety", (10, 185), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 165, 255), 2)
    if boundary_safety:
        cv2.putText(frame, "boundary safety", (10, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 0, 255), 2)

    if can_state is not None and target is not None:
        cv2.line(frame, can_state["center"], target["center"], (0, 255, 255), 2)
    elif can_state is not None and returning_home and home_center is not None:
        cv2.line(frame, can_state["center"], home_center, (255, 255, 0), 2)
    if can_state is not None and avoidance_target is not None:
        avoid_center = avoidance_target["center"]
        if avoid_center is not None:
            cv2.line(frame, can_state["center"], avoid_center, (0, 165, 255), 2)

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
    target_lost_since = None
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
            obstacles = (
                filter_obstacles_inside_can(can_state, result["obstacle_candidates"])
                if config.AVOID_WHITE_OBSTACLES
                else []
            )
            boundaries = result["boundary_candidates"] if config.ENABLE_WHITE_BOUNDARY else []
            boundary_mask = result["boundary_mask"] if config.ENABLE_WHITE_BOUNDARY else None
            if home_center is None and can_state is not None:
                home_center = can_state["center"]
                print(f"Home position set to {home_center}")

            now = time.time()
            if return_home_mode:
                target = None
                locked_target = None
                target_lost_since = None
            else:
                target = candidate_targets[0] if candidate_targets else None
                if target is not None:
                    target_seen_once = True
                    locked_target = target
                    missed_target_frames = 0
                    target_lost_since = None
                elif locked_target is not None and missed_target_frames < config.LOCK_MAX_MISSED_FRAMES:
                    target = locked_target
                    missed_target_frames += 1
                else:
                    locked_target = None
                    target = None
                    if config.RETURN_HOME_WHEN_TARGET_LOST:
                        if target_lost_since is None:
                            target_lost_since = now
                        elif now - target_lost_since >= config.TARGET_LOST_RETURN_HOME_SECONDS:
                            return_home_mode = True
                            target_lost_since = None
                            print("No target seen for 2.0s. Returning home.")
                    missed_target_frames = 0

            target_inside = False
            if can_state is not None and target is not None:
                if config.CAN_FOOTPRINT_SHAPE == "square":
                    footprint = square_can_footprint(can_state)
                    target_inside = footprint is not None and point_inside_square_can(target["center"], footprint)
                else:
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
                        if return_home_mode:
                            print("Target collected. Returning home.")
                        else:
                            print("Target reached. Stopping.")
                else:
                    target_inside_since = None

            returning_home = False
            view_safety = False
            boundary_safety = False
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

            if config.KEEP_TRASH_CAN_IN_VIEW and can_state is not None and target_seen_once:
                if can_near_camera_edge(can_state):
                    command_target = {"center": (int(config.FRAME_WIDTH / 2), int(config.FRAME_HEIGHT / 2))}
                    returning_home = False
                    view_safety = True

            avoidance_target = None
            if config.AVOID_WHITE_OBSTACLES and not view_safety:
                avoidance_target = choose_avoidance_target(can_state, command_target, obstacles)
                if avoidance_target is not None:
                    if avoidance_target.get("no_path") and config.RETURN_HOME_WHEN_OBSTACLE_BLOCKED:
                        locked_target = None
                        if return_home_mode:
                            command_target = None
                            returning_home = False
                            print("No predicted path home around obstacle. Stopping.")
                        else:
                            command_target = {"center": home_center} if home_center is not None else None
                            return_home_mode = home_center is not None
                            returning_home = home_center is not None
                            print("No predicted path around obstacle. Returning home." if home_center is not None else "No predicted path around obstacle. Stopping.")
                    else:
                        command_target = {"center": avoidance_target["center"]}
                        returning_home = False

            if (
                config.ENABLE_WHITE_BOUNDARY
                and can_state is not None
                and command_target is not None
                and path_crosses_boundary(can_state["center"], command_target["center"], boundary_mask)
            ):
                command_target = None
                returning_home = False
                avoidance_target = None
                boundary_safety = True

            obstacle_distance = closest_obstacle_distance(can_state, obstacles)
            obstacle_emergency_stop = (
                obstacle_distance is not None
                and obstacle_distance <= config.OBSTACLE_DANGER_DISTANCE_PX
            )
            stop_distance_px = config.VIEW_SAFE_STOP_PX if view_safety else config.HOME_STOP_PX if returning_home else None
            raw_command, telemetry = compute_command(can_state, command_target, stop_distance_px)
            if boundary_safety:
                raw_command = config.CMD_STOP
                telemetry = {"distance_px": None, "angle_deg": None, "turn_strength": 0}
            if obstacle_emergency_stop:
                raw_command = config.CMD_STOP
                telemetry = {"distance_px": obstacle_distance, "angle_deg": 0.0, "turn_strength": 0}
            if returning_home and raw_command == config.CMD_STOP:
                target_collected = False
                return_home_mode = False
                target_seen_once = False
                target_inside_since = None
                locked_target = None
                missed_target_frames = 0
                target_lost_since = None
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
                    f"missed={missed_target_frames} collected={target_collected} return_mode={return_home_mode} returning_home={returning_home} view_safety={view_safety} boundary_safety={boundary_safety} boundaries={len(boundaries)} obstacles={len(obstacles)} avoiding={avoidance_target is not None} obstacle_stop={obstacle_emergency_stop} "
                    f"command={command} raw={raw_command} "
                    f"distance={telemetry['distance_px']} angle={telemetry['angle_deg']} "
                    f"turn={telemetry['turn_strength']}"
                )
                last_status_print = now

            if window_enabled:
                overlay = frame.copy()
                draw_detection(overlay, can_state, target, command, telemetry, home_center, returning_home, target_collected, view_safety, obstacles, avoidance_target, boundaries, boundary_safety)
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
                    target_lost_since = None
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
