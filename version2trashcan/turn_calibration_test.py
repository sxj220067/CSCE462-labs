import argparse
import time

import config
from transport import create_transport, format_command


def clamp(value, lower, upper):
    return max(lower, min(upper, value))


def strength_from_angle(angle_deg):
    turn_ratio = min(1.0, abs(angle_deg) / config.FULL_TURN_ANGLE_DEG)
    strength = int(round(turn_ratio * 100 * config.TURN_STRENGTH_SCALE))
    return clamp(strength, config.MIN_TURN_STRENGTH, config.MAX_TURN_STRENGTH)


def parse_args():
    parser = argparse.ArgumentParser(description="Calibrate angle-based ESP32 curve turns.")
    parser.add_argument(
        "direction",
        choices=("L", "R"),
        help="Turn direction to test.",
    )
    parser.add_argument(
        "--angle",
        type=float,
        default=90.0,
        help="Pretend camera angle in degrees. Used to calculate turn strength.",
    )
    parser.add_argument(
        "--strength",
        type=int,
        default=None,
        help="Send a raw turn strength from 0 to 100 instead of calculating from angle.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=1.0,
        help="Seconds to run the turn before stopping.",
    )
    parser.add_argument(
        "--repeat-interval",
        type=float,
        default=0.10,
        help="Seconds between repeated command sends during the test.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.duration < 0.0:
        raise SystemExit("--duration must be non-negative")
    if args.repeat_interval <= 0.0:
        raise SystemExit("--repeat-interval must be greater than zero")

    if args.strength is None:
        strength = strength_from_angle(args.angle)
        source = f"angle={args.angle:.1f} deg"
    else:
        strength = clamp(args.strength, 0, 100)
        source = f"raw strength={args.strength}"

    telemetry = {"turn_strength": strength}
    payload = format_command(args.direction, telemetry)
    print(f"Turn calibration using transport={config.COMMAND_TRANSPORT}")
    print(f"{source} -> sending {payload} for {args.duration:.2f}s")
    print("Keep the robot lifted or in a clear area. Ctrl-C sends stop.")

    transport = create_transport()
    try:
        end_at = time.time() + args.duration
        while time.time() < end_at:
            transport.send(args.direction, telemetry)
            time.sleep(args.repeat_interval)
    except KeyboardInterrupt:
        print("Interrupted. Sending stop.")
    finally:
        transport.send(config.CMD_STOP)
        transport.close()


if __name__ == "__main__":
    main()
