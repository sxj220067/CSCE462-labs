import atexit

import config


MOVE_LEFT = "MOVE_LEFT"
MOVE_RIGHT = "MOVE_RIGHT"
MOVE_FORWARD = "MOVE_FORWARD"
MOVE_REVERSE = "MOVE_REVERSE"
STOP = "STOP"

_motor = None
_motor_init_error = None
_motor_warning_printed = False


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
        self._drive(False, False, config.MOTOR_FORWARD_DUTY, config.MOTOR_FORWARD_DUTY)

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
            motor._steer(MOVE_LEFT, turn_strength)
        elif command == MOVE_RIGHT:
            motor._steer(MOVE_RIGHT, turn_strength)
        elif command == MOVE_FORWARD:
            motor.move_forward()
        elif command == MOVE_REVERSE:
            motor.move_reverse()
        else:
            motor.stop()
    except Exception as exc:
        if not _motor_warning_printed:
            print(f"Motor command failed, falling back to stub output: {exc}")
            _motor_warning_printed = True
        print(f"[MOTOR_STUB] {command} offset={offset} strength={turn_strength:.2f}")
        return False

    return True
