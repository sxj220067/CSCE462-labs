import sys
import time

import config
from transport import create_transport


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else config.CMD_STOP
    if command not in {config.CMD_FORWARD, config.CMD_LEFT, config.CMD_RIGHT, config.CMD_STOP}:
        raise SystemExit(f"Unsupported command: {command}")

    transport = create_transport()
    try:
        print(f"Sending command {command} to {config.BLUETOOTH_MAC_ADDRESS}")
        transport.send(command)
        time.sleep(0.2)
    finally:
        transport.close()


if __name__ == "__main__":
    main()
