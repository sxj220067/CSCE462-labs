import time

import config


class StdoutTransport:
    def __init__(self):
        self._last_command = None

    def send(self, command):
        if command != self._last_command:
            print(f"[COMMAND] {command}")
            self._last_command = command

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

    def send(self, command):
        if command == self._last_command:
            return
        self._serial.write((command + "\n").encode("ascii"))
        self._last_command = command

    def close(self):
        if self._serial is not None:
            self._serial.close()


def create_transport():
    if config.COMMAND_TRANSPORT == "serial":
        return SerialTransport()
    return StdoutTransport()
