import time
import errno

import config


def format_command(command, telemetry=None):
    if config.SWAP_TURN_COMMANDS:
        if command == config.CMD_LEFT:
            command = config.CMD_RIGHT
        elif command == config.CMD_RIGHT:
            command = config.CMD_LEFT
    if command in {config.CMD_LEFT, config.CMD_RIGHT} and telemetry is not None:
        return f"{command}:{int(telemetry.get('turn_strength', 100))}"
    return command


class StdoutTransport:
    def __init__(self):
        self._last_command = None

    def send(self, command, telemetry=None):
        payload = format_command(command, telemetry)
        if payload != self._last_command:
            print(f"[COMMAND] {payload}")
            self._last_command = payload

    def close(self):
        return None


class SerialTransport:
    def __init__(self):
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError("pyserial is required for serial transport.") from exc

        self._serial = serial.Serial(
            config.SERIAL_PORT,
            config.SERIAL_BAUDRATE,
            timeout=config.SERIAL_TIMEOUT_S,
        )
        self._last_command = None
        time.sleep(2.0)

    def send(self, command, telemetry=None):
        payload = format_command(command, telemetry)
        if payload == self._last_command:
            return
        self._serial.write((payload + "\n").encode("ascii"))
        self._last_command = payload

    def close(self):
        if self._serial is not None:
            self._serial.close()


class BluetoothTransport:
    def __init__(self):
        import socket

        if not getattr(socket, "AF_BLUETOOTH", None):
            raise RuntimeError("This Python build does not support Bluetooth sockets.")

        self._socket_module = socket
        self._sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        self._sock.settimeout(config.BLUETOOTH_CONNECT_TIMEOUT_S)
        try:
            self._sock.connect((config.BLUETOOTH_MAC_ADDRESS, config.BLUETOOTH_CHANNEL))
        except OSError as exc:
            self._sock.close()
            if exc.errno == errno.EBUSY:
                raise RuntimeError(
                    "ESP32 Bluetooth is busy. Close any running main.py/movement test, "
                    "then run: bluetoothctl disconnect "
                    f"{config.BLUETOOTH_MAC_ADDRESS}"
                ) from exc
            raise
        self._sock.settimeout(None)
        self._last_command = None

    def send(self, command, telemetry=None):
        payload = format_command(command, telemetry)
        if payload == self._last_command:
            return
        self._sock.sendall((payload + "\n").encode("ascii"))
        self._last_command = payload

    def close(self):
        if self._sock is not None:
            self._sock.close()


class GpioMotorTransport:
    def __init__(self):
        try:
            import RPi.GPIO as GPIO
        except ImportError as exc:
            raise RuntimeError("RPi.GPIO is required for gpio motor transport. Install it on the Raspberry Pi.") from exc

        self._gpio = GPIO
        self._last_command = None
        self._left_pwm = None
        self._right_pwm = None

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        self._output_pins = (
            config.GPIO_LEFT_IN1,
            config.GPIO_LEFT_IN2,
            config.GPIO_RIGHT_IN1,
            config.GPIO_RIGHT_IN2,
            config.GPIO_LEFT_ENABLE,
            config.GPIO_RIGHT_ENABLE,
        )
        for pin in self._output_pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)

        self._left_pwm = GPIO.PWM(config.GPIO_LEFT_ENABLE, config.GPIO_PWM_FREQUENCY_HZ)
        self._right_pwm = GPIO.PWM(config.GPIO_RIGHT_ENABLE, config.GPIO_PWM_FREQUENCY_HZ)
        self._left_pwm.start(0)
        self._right_pwm.start(0)
        self.stop()

    def _set_left_motor(self, forward, duty):
        self._gpio.output(config.GPIO_LEFT_IN1, self._gpio.HIGH if forward else self._gpio.LOW)
        self._gpio.output(config.GPIO_LEFT_IN2, self._gpio.LOW if forward else self._gpio.HIGH)
        self._left_pwm.ChangeDutyCycle(duty)

    def _set_right_motor(self, forward, duty):
        self._gpio.output(config.GPIO_RIGHT_IN1, self._gpio.HIGH if forward else self._gpio.LOW)
        self._gpio.output(config.GPIO_RIGHT_IN2, self._gpio.LOW if forward else self._gpio.HIGH)
        self._right_pwm.ChangeDutyCycle(duty)

    def _turn_duty(self, telemetry):
        strength = 100 if telemetry is None else int(telemetry.get("turn_strength", 100))
        strength = max(config.MIN_TURN_STRENGTH, min(100, strength))
        ratio = (strength - config.MIN_TURN_STRENGTH) / max(1, 100 - config.MIN_TURN_STRENGTH)
        return config.GPIO_TURN_MIN_DUTY + (ratio * (config.GPIO_TURN_MAX_DUTY - config.GPIO_TURN_MIN_DUTY))

    def stop(self):
        self._left_pwm.ChangeDutyCycle(0)
        self._right_pwm.ChangeDutyCycle(0)
        self._gpio.output(config.GPIO_LEFT_IN1, self._gpio.LOW)
        self._gpio.output(config.GPIO_LEFT_IN2, self._gpio.LOW)
        self._gpio.output(config.GPIO_RIGHT_IN1, self._gpio.LOW)
        self._gpio.output(config.GPIO_RIGHT_IN2, self._gpio.LOW)

    def send(self, command, telemetry=None):
        payload = format_command(command, telemetry)
        if payload == self._last_command:
            return
        self._last_command = payload
        self.send_payload(payload, telemetry)

    def send_payload(self, payload, telemetry=None):
        command = payload[0]
        if command == config.CMD_FORWARD:
            self._set_left_motor(True, config.GPIO_DRIVE_DUTY)
            self._set_right_motor(True, config.GPIO_DRIVE_DUTY)
        elif command == config.CMD_LEFT:
            turn_duty = self._turn_duty(telemetry)
            self._set_left_motor(False, turn_duty)
            self._set_right_motor(True, turn_duty)
        elif command == config.CMD_RIGHT:
            turn_duty = self._turn_duty(telemetry)
            self._set_left_motor(True, turn_duty)
            self._set_right_motor(False, turn_duty)
        else:
            self.stop()

    def close(self):
        self.stop()
        if self._left_pwm is not None:
            self._left_pwm.stop()
        if self._right_pwm is not None:
            self._right_pwm.stop()
        self._gpio.cleanup(self._output_pins)


class TcpTransport:
    def __init__(self):
        import socket

        self._socket_module = socket
        self._sock = socket.create_connection(
            (config.MOTOR_SERVER_HOST, config.MOTOR_SERVER_PORT),
            timeout=config.MOTOR_SERVER_CONNECT_TIMEOUT_S,
        )
        self._sock.settimeout(None)
        self._last_command = None

    def send(self, command, telemetry=None):
        payload = format_command(command, telemetry)
        if payload == self._last_command:
            return
        self._sock.sendall((payload + "\n").encode("ascii"))
        self._last_command = payload

    def close(self):
        if self._sock is not None:
            self._sock.close()


class PiBluetoothTransport:
    def __init__(self):
        import socket

        if not getattr(socket, "AF_BLUETOOTH", None):
            raise RuntimeError("This Python build does not support Bluetooth sockets.")

        self._sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        self._sock.settimeout(config.MOTOR_BLUETOOTH_CONNECT_TIMEOUT_S)
        self._sock.connect((config.MOTOR_BLUETOOTH_ADDRESS, config.MOTOR_BLUETOOTH_CHANNEL))
        self._sock.settimeout(None)
        self._last_command = None

    def send(self, command, telemetry=None):
        payload = format_command(command, telemetry)
        if payload == self._last_command:
            return
        self._sock.sendall((payload + "\n").encode("ascii"))
        self._last_command = payload

    def close(self):
        if self._sock is not None:
            self._sock.close()


def create_transport():
    if config.COMMAND_TRANSPORT == "serial":
        return SerialTransport()
    if config.COMMAND_TRANSPORT == "bluetooth":
        return BluetoothTransport()
    if config.COMMAND_TRANSPORT == "gpio":
        return GpioMotorTransport()
    if config.COMMAND_TRANSPORT == "tcp":
        return TcpTransport()
    if config.COMMAND_TRANSPORT == "pi_bluetooth":
        return PiBluetoothTransport()
    return StdoutTransport()
