import math

import config


def distance(point_a, point_b):
    dx = point_b[0] - point_a[0]
    dy = point_b[1] - point_a[1]
    return math.hypot(dx, dy)


def signed_angle_deg(heading, target_vector):
    heading_angle = math.atan2(heading[1], heading[0])
    target_angle = math.atan2(target_vector[1], target_vector[0])
    angle = math.degrees(target_angle - heading_angle)
    while angle > 180.0:
        angle -= 360.0
    while angle < -180.0:
        angle += 360.0
    return angle


def clamp(value, lower, upper):
    return max(lower, min(upper, value))


def choose_target(candidates, locked_target):
    if not candidates:
        return None
    if locked_target is None or not config.LOCK_ON_FIRST_TARGET:
        return candidates[0]

    locked_center = locked_target["center"]
    best_candidate = None
    best_distance = None
    for candidate in candidates:
        jump = distance(locked_center, candidate["center"])
        if jump > config.LOCK_MAX_JUMP_PX:
            continue
        if best_distance is None or jump < best_distance:
            best_distance = jump
            best_candidate = candidate
    return best_candidate


def compute_command(can_state, target, stop_distance_px=None):
    if can_state is None or target is None:
        return config.CMD_STOP, {"distance_px": None, "angle_deg": None, "turn_strength": 0}

    can_center = can_state["center"]
    heading = can_state["heading"]
    target_center = target["center"]
    target_vector = (
        target_center[0] - can_center[0],
        target_center[1] - can_center[1],
    )

    stop_distance = config.DISTANCE_STOP_PX if stop_distance_px is None else stop_distance_px
    dist_px = distance(can_center, target_center)
    if dist_px <= stop_distance:
        return config.CMD_STOP, {"distance_px": dist_px, "angle_deg": 0.0, "turn_strength": 0}

    angle_deg = signed_angle_deg(heading, target_vector)
    if abs(angle_deg) <= config.HEADING_ALIGNMENT_DEG:
        return config.CMD_FORWARD, {"distance_px": dist_px, "angle_deg": angle_deg, "turn_strength": 0}

    turn_ratio = min(1.0, abs(angle_deg) / config.FULL_TURN_ANGLE_DEG)
    turn_strength = int(round(turn_ratio * 100 * config.TURN_STRENGTH_SCALE))
    turn_strength = clamp(turn_strength, config.MIN_TURN_STRENGTH, config.MAX_TURN_STRENGTH)

    if config.FORWARD_ONLY_WHEN_ALIGNED:
        command = config.CMD_LEFT if angle_deg < 0.0 else config.CMD_RIGHT
        return command, {"distance_px": dist_px, "angle_deg": angle_deg, "turn_strength": turn_strength}

    return config.CMD_FORWARD, {"distance_px": dist_px, "angle_deg": angle_deg, "turn_strength": turn_strength}
