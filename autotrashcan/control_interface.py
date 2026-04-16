import atexit

import config


MOVE_LEFT = "MOVE_LEFT"
MOVE_RIGHT = "MOVE_RIGHT"
MOVE_FORWARD = "MOVE_FORWARD"
STOP = "STOP"

_motor = None
_motor_init_error = None


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

    def _drive(self, left_forward, right_forward, left_duty, right_duty):
        self._set_channel(
            self.left_in1,
            self.left_in2,
            self.left_enable,
            left_forward,
            left_duty,
            config.LEFT_MOTOR_INVERTED,
        )
        self._set_channel(
            self.right_in3,
            self.right_in4,
            self.right_enable,
            right_forward,
            right_duty,
            config.RIGHT_MOTOR_INVERTED,
        )

    def move_left(self):
        self._drive(False, True, config.MOTOR_TURN_DUTY, config.MOTOR_TURN_DUTY)

    def move_right(self):
        self._drive(True, False, config.MOTOR_TURN_DUTY, config.MOTOR_TURN_DUTY)

    def move_forward(self):
        self._drive(True, True, config.MOTOR_FORWARD_DUTY, config.MOTOR_FORWARD_DUTY)

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
        return STOP, 0

    center_x = frame_width // 2
    offset = int(predicted_x - center_x)

    if abs(offset) <= deadzone_px:
        return MOVE_FORWARD, 0

    if offset < 0:
        return MOVE_LEFT, offset

    return MOVE_RIGHT, offset


def send_motor_command(command, offset=0):
    if config.MOTOR_MOCK:
        print(f"[MOTOR_STUB] {command} offset={offset}")
        return True

    motor = get_motor_controller()

    if command == MOVE_LEFT:
        motor.move_left()
    elif command == MOVE_RIGHT:
        motor.move_right()
    elif command == MOVE_FORWARD:
        motor.move_forward()
    else:
        motor.stop()

    return True
