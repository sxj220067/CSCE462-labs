import argparse
import time

import config
from transport import create_transport


MOVEMENT_COMMANDS = {
    config.CMD_FORWARD: "forward",
    config.CMD_LEFT: "left",
    config.CMD_RIGHT: "right",
    config.CMD_STOP: "stop",
    "T": "esp32 self-test",
}


def send_for_duration(transport, command, duration, repeat_interval):
    label = MOVEMENT_COMMANDS[command]
    print(f"Sending {command} ({label}) for {duration:.2f}s")
    end_at = time.time() + duration
    while time.time() < end_at:
        transport.send(command)
        time.sleep(repeat_interval)
    if command not in {config.CMD_STOP, "T"}:
        print("Sending S (stop)")
        transport.send(config.CMD_STOP)
        time.sleep(0.2)


def run_sequence(transport, duration, pause, repeat_interval):
    sequence = (config.CMD_FORWARD, config.CMD_LEFT, config.CMD_RIGHT)
    for command in sequence:
        send_for_duration(transport, command, duration, repeat_interval)
        print(f"Pausing {pause:.2f}s")
        time.sleep(pause)
    send_for_duration(transport, config.CMD_STOP, 0.2, repeat_interval)


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
        default=2.0,
        help="Seconds to run each movement command before stopping.",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=0.75,
        help="Seconds to pause between commands in the full sequence.",
    )
    parser.add_argument(
        "--repeat-interval",
        type=float,
        default=0.10,
        help="Seconds between repeated command sends during movement.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.duration < 0.0:
        raise SystemExit("--duration must be non-negative")
    if args.pause < 0.0:
        raise SystemExit("--pause must be non-negative")
    if args.repeat_interval <= 0.0:
        raise SystemExit("--repeat-interval must be greater than zero")

    transport = create_transport()
    try:
        print(f"Movement test using transport={config.COMMAND_TRANSPORT}")
        print("Keep the robot lifted or in a clear area. Ctrl-C sends stop.")
        if args.command is None:
            run_sequence(transport, args.duration, args.pause, args.repeat_interval)
        else:
            send_for_duration(transport, args.command, args.duration, args.repeat_interval)
    except KeyboardInterrupt:
        print("Interrupted. Sending stop.")
    finally:
        transport.send(config.CMD_STOP)
        transport.close()


if __name__ == "__main__":
    main()
