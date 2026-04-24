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


class BluetoothTransport:
    def __init__(self):
        import socket

        if not getattr(socket, "AF_BLUETOOTH", None):
            raise RuntimeError("This Python build does not support Bluetooth sockets.")

        self._socket_module = socket
        self._sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        self._sock.settimeout(config.BLUETOOTH_CONNECT_TIMEOUT_S)
        self._sock.connect((config.BLUETOOTH_MAC_ADDRESS, config.BLUETOOTH_CHANNEL))
        self._sock.settimeout(None)
        self._last_command = None

    def send(self, command):
        if command == self._last_command:
            return
        self._sock.sendall((command + "\n").encode("ascii"))
        self._last_command = command

    def close(self):
        if self._sock is not None:
            self._sock.close()


def create_transport():
    if config.COMMAND_TRANSPORT == "serial":
        return SerialTransport()
    if config.COMMAND_TRANSPORT == "bluetooth":
        return BluetoothTransport()
    return StdoutTransport()
