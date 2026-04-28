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
    print(f"[MOTOR SERVER] connected: {address}")
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
                    print(f"[MOTOR SERVER] command={line.strip()}")
                    transport.send_payload(line.strip(), telemetry)
    finally:
        transport.send(config.CMD_STOP)
        print(f"[MOTOR SERVER] disconnected: {address}")


def main():
    transport = GpioMotorTransport()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", config.MOTOR_SERVER_PORT))
            server.listen(1)
            print(f"[MOTOR SERVER] listening on 0.0.0.0:{config.MOTOR_SERVER_PORT}")
            while True:
                conn, address = server.accept()
                thread = threading.Thread(target=handle_client, args=(conn, address, transport), daemon=True)
                thread.start()
    except KeyboardInterrupt:
        print("[MOTOR SERVER] stopping")
    finally:
        transport.send(config.CMD_STOP)
        transport.close()


if __name__ == "__main__":
    main()
