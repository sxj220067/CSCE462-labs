import argparse
import time

import config
from transport import create_transport


MOVEMENT_COMMANDS = {
    config.CMD_FORWARD: "forward",
    config.CMD_LEFT: "left",
    config.CMD_RIGHT: "right",
    config.CMD_STOP: "stop",
}


def send_for_duration(transport, command, duration):
    label = MOVEMENT_COMMANDS[command]
    print(f"Sending {command} ({label}) for {duration:.2f}s")
    transport.send(command)
    time.sleep(duration)
    if command != config.CMD_STOP:
        print("Sending S (stop)")
        transport.send(config.CMD_STOP)
        time.sleep(0.2)


def run_sequence(transport, duration, pause):
    sequence = (config.CMD_FORWARD, config.CMD_LEFT, config.CMD_RIGHT)
    for command in sequence:
        send_for_duration(transport, command, duration)
        print(f"Pausing {pause:.2f}s")
        time.sleep(pause)
    send_for_duration(transport, config.CMD_STOP, 0.2)


def parse_args():
    parser = argparse.ArgumentParser(description="Safely test trash can movement commands.")
    parser.add_argument(
        "command",
        nargs="?",
        choices=tuple(MOVEMENT_COMMANDS.keys()),
        help="Command to test: F, L, R, or S. If omitted, runs the full movement sequence.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.75,
        help="Seconds to run each movement command before stopping.",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=0.75,
        help="Seconds to pause between commands in the full sequence.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.duration < 0.0:
        raise SystemExit("--duration must be non-negative")
    if args.pause < 0.0:
        raise SystemExit("--pause must be non-negative")

    transport = create_transport()
    try:
        print(f"Movement test using transport={config.COMMAND_TRANSPORT}")
        print("Keep the robot lifted or in a clear area. Ctrl-C sends stop.")
        if args.command is None:
            run_sequence(transport, args.duration, args.pause)
        else:
            send_for_duration(transport, args.command, args.duration)
    except KeyboardInterrupt:
        print("Interrupted. Sending stop.")
    finally:
        transport.send(config.CMD_STOP)
        transport.close()


if __name__ == "__main__":
    main()
