import socket
import threading

import config
from transport import GpioMotorTransport


def parse_payload(payload):
    payload = payload.strip()
    if not payload:
        return None, None

    command = payload[0]
    telemetry = None
    if ":" in payload:
        _, strength_text = payload.split(":", 1)
        try:
            telemetry = {"turn_strength": int(strength_text)}
        except ValueError:
            telemetry = None
    return command, telemetry


def handle_client(conn, address, transport):
    print(f"[MOTOR BT SERVER] connected: {address}")
    buffer = ""
    try:
        with conn:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                buffer += data.decode("ascii", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    command, telemetry = parse_payload(line)
                    if command is None:
                        continue
                    print(f"[MOTOR BT SERVER] command={line.strip()}")
                    transport.send_payload(line.strip(), telemetry)
    finally:
        transport.send(config.CMD_STOP)
        print(f"[MOTOR BT SERVER] disconnected: {address}")


def main():
    if not getattr(socket, "AF_BLUETOOTH", None):
        raise RuntimeError("This Python build does not support Bluetooth sockets.")

    transport = GpioMotorTransport()
    server = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    try:
        server.bind(("00:00:00:00:00:00", config.MOTOR_BLUETOOTH_CHANNEL))
        server.listen(1)
        print(f"[MOTOR BT SERVER] listening on RFCOMM channel {config.MOTOR_BLUETOOTH_CHANNEL}")
        while True:
            conn, address = server.accept()
            thread = threading.Thread(target=handle_client, args=(conn, address, transport), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        print("[MOTOR BT SERVER] stopping")
    finally:
        transport.send(config.CMD_STOP)
        transport.close()
        server.close()


if __name__ == "__main__":
    main()
