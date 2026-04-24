import atexit
import math

import config


MOVE_LEFT = "MOVE_LEFT"
MOVE_RIGHT = "MOVE_RIGHT"
MOVE_FORWARD = "MOVE_FORWARD"
MOVE_REVERSE = "MOVE_REVERSE"
STOP = "STOP"

_motor = None
_motor_init_error = None
_motor_warning_printed = False


def _overhead_forward_sign():
    return -1 if config.OVERHEAD_FRONT_IS_NEGATIVE_Y else 1


def _overhead_stop_y_offset():
    return _overhead_forward_sign() * abs(config.OVERHEAD_STOP_Y_OFFSET_PX)


def _safe_device_call(device, method_name):
    if device is None:
        return

    method = getattr(device, method_name, None)
    if method is None:
        return

    try:
        method()
    except Exception:
        # Best-effort cleanup: GPIO devices may already be closed during shutdown.
        pass


class L298NMotorController:
    def __init__(self):
        try:
            from gpiozero import DigitalOutputDevice, PWMOutputDevice
        except ImportError as exc:
            raise RuntimeError(
                "gpiozero is not installed. On Raspberry Pi OS, run: sudo apt install -y python3-gpiozero"
            ) from exc

        self.left_in1 = DigitalOutputDevice(config.L298N_LEFT_IN1_PIN)
        self.left_in2 = DigitalOutputDevice(config.L298N_LEFT_IN2_PIN)
        self.left_enable = PWMOutputDevice(
            config.L298N_LEFT_ENABLE_PIN,
            frequency=config.L298N_PWM_FREQUENCY,
            initial_value=0,
        )
        self.right_in3 = DigitalOutputDevice(config.L298N_RIGHT_IN3_PIN)
        self.right_in4 = DigitalOutputDevice(config.L298N_RIGHT_IN4_PIN)
        self.right_enable = PWMOutputDevice(
            config.L298N_RIGHT_ENABLE_PIN,
            frequency=config.L298N_PWM_FREQUENCY,
            initial_value=0,
        )
        self.stop()

    def _set_channel(self, pin_a, pin_b, enable, forward, duty_cycle, inverted=False):
        duty_cycle = max(0.0, min(1.0, duty_cycle))
        if duty_cycle == 0.0:
            enable.off()
            pin_a.off()
            pin_b.off()
            return

        if inverted:
            forward = not forward

        if forward:
            pin_a.on()
            pin_b.off()
        else:
            pin_a.off()
            pin_b.on()
        enable.value = duty_cycle

    def _apply_scale(self, duty_cycle, scale):
        return max(0.0, min(1.0, duty_cycle * scale))

    def _steer(self, direction, turn_strength):
        turn_strength = max(config.MIN_TURN_STRENGTH, min(config.MAX_TURN_STRENGTH, turn_strength))
        outer_duty = config.MOTOR_TURN_DUTY
        arc_ratio = max(0.0, 1.0 - turn_strength)
        inner_forward_duty = outer_duty * config.TURN_FORWARD_BIAS * arc_ratio
        reverse_threshold = 0.75

        if turn_strength >= reverse_threshold:
            reverse_ratio = (turn_strength - reverse_threshold) / max(1.0 - reverse_threshold, 1e-6)
            inner_forward = False
            inner_duty = outer_duty * reverse_ratio
        else:
            inner_forward = True
            inner_duty = inner_forward_duty

        if direction == MOVE_LEFT:
            self._drive(inner_forward, True, inner_duty, outer_duty)
        else:
            self._drive(True, inner_forward, outer_duty, inner_duty)

    def _drive(self, left_forward, right_forward, left_duty, right_duty):
        self._set_channel(
            self.left_in1,
            self.left_in2,
            self.left_enable,
            left_forward,
            self._apply_scale(left_duty, config.LEFT_MOTOR_SCALE),
            config.LEFT_MOTOR_INVERTED,
        )
        self._set_channel(
            self.right_in3,
            self.right_in4,
            self.right_enable,
            right_forward,
            self._apply_scale(right_duty, config.RIGHT_MOTOR_SCALE),
            config.RIGHT_MOTOR_INVERTED,
        )

    def move_left(self):
        self._drive(False, True, config.MOTOR_TURN_DUTY, config.MOTOR_TURN_DUTY)

    def move_right(self):
        self._drive(True, False, config.MOTOR_TURN_DUTY, config.MOTOR_TURN_DUTY)

    def move_forward(self):
        self._drive(True, True, config.MOTOR_FORWARD_DUTY, config.MOTOR_FORWARD_DUTY)

    def move_reverse(self):
        self._drive(False, False, config.MOTOR_REVERSE_DUTY, config.MOTOR_REVERSE_DUTY)

    def stop(self):
        _safe_device_call(self.left_enable, "off")
        _safe_device_call(self.left_in1, "off")
        _safe_device_call(self.left_in2, "off")
        _safe_device_call(self.right_enable, "off")
        _safe_device_call(self.right_in3, "off")
        _safe_device_call(self.right_in4, "off")

    def close(self):
        self.stop()
        _safe_device_call(self.left_enable, "close")
        _safe_device_call(self.left_in1, "close")
        _safe_device_call(self.left_in2, "close")
        _safe_device_call(self.right_enable, "close")
        _safe_device_call(self.right_in3, "close")
        _safe_device_call(self.right_in4, "close")


def get_motor_controller():
    global _motor, _motor_init_error

    if _motor is not None:
        return _motor

    if _motor_init_error is not None:
        raise _motor_init_error

    if config.MOTOR_DRIVER.lower() != "l298n":
        _motor_init_error = RuntimeError(f"Unsupported motor driver: {config.MOTOR_DRIVER}")
        raise _motor_init_error

    try:
        _motor = L298NMotorController()
        return _motor
    except Exception as exc:
        _motor_init_error = exc
        raise


def cleanup_motor():
    global _motor
    if _motor is not None:
        try:
            _motor.close()
        except Exception:
            pass
        _motor = None


atexit.register(cleanup_motor)


def compute_move_command(predicted_x, frame_width, deadzone_px=config.CENTER_DEADZONE_PX):
    if predicted_x is None:
        return STOP, 0, 0.0

    center_x = frame_width // 2
    offset = int(predicted_x - center_x)
    max_offset = max(frame_width // 2, 1)
    normalized_offset = min(1.0, abs(offset) / float(max_offset))

    if abs(offset) <= deadzone_px:
        return MOVE_FORWARD, 0, 0.0

    turn_strength = config.MIN_TURN_STRENGTH + (
        (config.MAX_TURN_STRENGTH - config.MIN_TURN_STRENGTH) * normalized_offset
    )
    turn_strength = max(config.MIN_TURN_STRENGTH, min(config.MAX_TURN_STRENGTH, turn_strength))

    if offset < 0:
        return MOVE_LEFT, offset, turn_strength

    return MOVE_RIGHT, offset, turn_strength


def plan_path_to_target(target_point, frame_width, frame_height):
    if target_point is None:
        return []

    if config.CAMERA_FACING_UP:
        robot_origin = (frame_width // 2, frame_height // 2)
        return [robot_origin, target_point]

    robot_origin = (frame_width // 2, frame_height - 1)
    target_x, target_y = target_point
    lookahead_y = int(frame_height - ((frame_height - target_y) * config.PATH_GUIDE_LOOKAHEAD_RATIO))
    lookahead_y = max(target_y, min(frame_height - 1, lookahead_y))

    return [
        robot_origin,
        (robot_origin[0], lookahead_y),
        (target_x, target_y),
    ]


def compute_overhead_command(target_point, frame_width, frame_height):
    if target_point is None:
        return STOP, 0, 0.0

    center_x = frame_width // 2
    center_y = frame_height // 2
    dx = int(target_point[0] - center_x)
    dy = int(target_point[1] - center_y)
    forward_axis = _overhead_forward_sign() * dy
    stop_dx = dx
    stop_dy = dy - _overhead_stop_y_offset()
    stop_error = math.hypot(stop_dx, stop_dy)

    if is_within_overhead_stop_zone(target_point, frame_width, frame_height):
        return STOP, 0, 0.0

    heading_angle_deg = math.degrees(math.atan2(dx, -dy))
    angle_magnitude = abs(heading_angle_deg)
    soft_align_zone = max(config.OVERHEAD_AXIS_DEADZONE_PX, config.OVERHEAD_SOFT_ALIGN_ZONE_PX)
    pivot_turn_threshold = max(soft_align_zone + 1, config.OVERHEAD_PIVOT_TURN_THRESHOLD_PX)

    if angle_magnitude > config.OVERHEAD_ALIGN_ANGLE_DEG and abs(dx) > pivot_turn_threshold:
        pivot_ratio = min(
            1.0,
            (abs(dx) - pivot_turn_threshold) / float(max((frame_width / 2.0) - pivot_turn_threshold, 1.0)),
        )
        turn_strength = config.OVERHEAD_PIVOT_TURN_MIN_STRENGTH + (
            (config.OVERHEAD_PIVOT_TURN_MAX_STRENGTH - config.OVERHEAD_PIVOT_TURN_MIN_STRENGTH)
            * pivot_ratio
        )
        if dx < 0:
            return MOVE_LEFT, dx, turn_strength
        return MOVE_RIGHT, dx, turn_strength

    slowdown_radius = max(
        config.OVERHEAD_APPROACH_SLOWDOWN_RADIUS_PX,
        config.OVERHEAD_CENTER_RADIUS_PX + 1,
    )
    approach_scale = min(1.0, stop_error / float(max(slowdown_radius, 1)))
    approach_scale = max(config.OVERHEAD_APPROACH_MIN_SPEED_SCALE, approach_scale)
    lateral_ratio = min(1.0, abs(dx) / max(frame_width / 2.0, 1.0))
    approach_turn_strength = config.OVERHEAD_ARC_TURN_MIN_STRENGTH + (
        (config.OVERHEAD_ARC_TURN_MAX_STRENGTH - config.OVERHEAD_ARC_TURN_MIN_STRENGTH)
        * lateral_ratio
    )
    if abs(dx) <= soft_align_zone:
        approach_turn_strength = 0.0

    if forward_axis > config.OVERHEAD_AXIS_DEADZONE_PX:
        return MOVE_FORWARD, dx, min(1.0, approach_scale * max(approach_turn_strength, 0.0))

    if forward_axis < -config.OVERHEAD_AXIS_DEADZONE_PX:
        if config.OVERHEAD_REVERSE_ENABLED:
            return MOVE_REVERSE, dx, min(1.0, approach_scale * max(approach_turn_strength, 0.0))

        turn_strength = config.MIN_TURN_STRENGTH + (
            (config.MAX_TURN_STRENGTH - config.MIN_TURN_STRENGTH)
            * min(1.0, angle_magnitude / 90.0)
        )
        if dx < 0:
            return MOVE_RIGHT, dx, turn_strength
        return MOVE_LEFT, dx, turn_strength

    if abs(dx) <= soft_align_zone:
        return STOP, 0, 0.0

    pivot_ratio = min(
        1.0,
        max(0.0, abs(dx) - soft_align_zone) / float(max((frame_width / 2.0) - soft_align_zone, 1.0)),
    )
    turn_strength = config.OVERHEAD_PIVOT_TURN_MIN_STRENGTH + (
        (config.OVERHEAD_PIVOT_TURN_MAX_STRENGTH - config.OVERHEAD_PIVOT_TURN_MIN_STRENGTH)
        * pivot_ratio
    )
    if dx < 0:
        return MOVE_LEFT, dx, turn_strength
    return MOVE_RIGHT, dx, turn_strength


def is_within_overhead_stop_zone(target_point, frame_width, frame_height):
    if target_point is None:
        return False

    center_x = frame_width // 2
    center_y = frame_height // 2
    dx = int(target_point[0] - center_x)
    dy = int(target_point[1] - center_y)
    stop_dx = dx
    stop_dy = dy - _overhead_stop_y_offset()
    stop_error = math.hypot(stop_dx, stop_dy)

    return (
        (
            abs(stop_dx) <= config.OVERHEAD_AXIS_DEADZONE_PX
            and abs(stop_dy) <= config.OVERHEAD_STOP_Y_TOLERANCE_PX
        )
        or stop_error <= config.OVERHEAD_CENTER_RADIUS_PX
    )


def compute_path_command(path_points, frame_width, frame_height, target_bbox=None):
    if len(path_points) < 2:
        return STOP, 0, 0.0

    if config.CAMERA_FACING_UP:
        return compute_overhead_command(path_points[-1], frame_width, frame_height)

    robot_origin = path_points[0]
    waypoint = path_points[1]
    goal = path_points[-1]

    close_to_goal = False
    if target_bbox is not None:
        x, y, w, h = target_bbox
        target_center_y = int(y + (h / 2))
        bbox_area = w * h
        close_to_goal = (
            target_center_y >= int(frame_height * config.TARGET_CLOSE_Y_RATIO)
            or bbox_area >= config.TARGET_CLOSE_AREA
        )

    active_point = goal if close_to_goal else waypoint
    offset = int(active_point[0] - robot_origin[0])
    turn_threshold = max(config.CENTER_DEADZONE_PX, int(frame_width * config.PATH_TURN_CLOSE_RATIO))

    if abs(offset) <= config.TARGET_STOP_X_DEADZONE_PX and close_to_goal:
        return STOP, 0, 0.0

    if abs(offset) <= config.CENTER_DEADZONE_PX:
        return MOVE_FORWARD, offset, 0.0

    command, offset, turn_strength = compute_move_command(active_point[0], frame_width, deadzone_px=turn_threshold)
    turn_strength = max(config.PATH_MIN_TURN_STRENGTH, turn_strength)

    if close_to_goal:
        return command, offset, turn_strength

    if config.APPROACH_ALIGNED_ONLY:
        return command, offset, turn_strength

    return MOVE_FORWARD, offset, turn_strength


def compute_approach_command(target_bbox, frame_width, frame_height):
    if target_bbox is None:
        return STOP, 0, 0.0

    x, y, w, h = target_bbox
    target_center_x = int(x + (w / 2))
    target_center_y = int(y + (h / 2))
    bbox_area = w * h
    frame_center_x = frame_width // 2
    x_offset = target_center_x - frame_center_x

    command, offset, turn_strength = compute_move_command(target_center_x, frame_width)

    close_in_frame = (
        target_center_y >= int(frame_height * config.TARGET_CLOSE_Y_RATIO)
        or bbox_area >= config.TARGET_CLOSE_AREA
    )
    horizontally_aligned = abs(x_offset) <= config.TARGET_STOP_X_DEADZONE_PX

    if close_in_frame and horizontally_aligned:
        return STOP, 0, 0.0

    if config.APPROACH_ALIGNED_ONLY and command != MOVE_FORWARD:
        return command, offset, turn_strength

    return MOVE_FORWARD, offset, turn_strength


def send_motor_command(command, offset=0, turn_strength=0.0):
    global _motor_warning_printed

    if config.MOTOR_MOCK:
        print(f"[MOTOR_STUB] {command} offset={offset} strength={turn_strength:.2f}")
        return True

    try:
        motor = get_motor_controller()
    except Exception as exc:
        if not _motor_warning_printed:
            print(f"Motor controller unavailable, falling back to stub output: {exc}")
            _motor_warning_printed = True
        print(f"[MOTOR_STUB] {command} offset={offset} strength={turn_strength:.2f}")
        return False

    try:
        if command == MOVE_LEFT:
            motor.move_left()
        elif command == MOVE_RIGHT:
            motor.move_right()
        elif command == MOVE_FORWARD:
            duty = config.MOTOR_FORWARD_DUTY
            if turn_strength > 0.0 and offset != 0:
                outer_duty = duty
                inner_ratio = max(0.45, 1.0 - (turn_strength * 0.7))
                inner_duty = duty * inner_ratio
                if offset < 0:
                    motor._drive(True, True, inner_duty, outer_duty)
                else:
                    motor._drive(True, True, outer_duty, inner_duty)
            else:
                motor._drive(True, True, duty, duty)
        elif command == MOVE_REVERSE:
            duty = config.MOTOR_REVERSE_DUTY
            if turn_strength > 0.0 and offset != 0:
                outer_duty = duty
                inner_ratio = max(0.45, 1.0 - (turn_strength * 0.7))
                inner_duty = duty * inner_ratio
                if offset < 0:
                    motor._drive(False, False, inner_duty, outer_duty)
                else:
                    motor._drive(False, False, outer_duty, inner_duty)
            else:
                motor._drive(False, False, duty, duty)
        else:
            motor.stop()
    except Exception as exc:
        if not _motor_warning_printed:
            print(f"Motor command failed, falling back to stub output: {exc}")
            _motor_warning_printed = True
        print(f"[MOTOR_STUB] {command} offset={offset} strength={turn_strength:.2f}")
        return False

    return True
