import argparse

import config
from transport import create_transport


def parse_args():
    parser = argparse.ArgumentParser(description="Send one movement command using the configured transport.")
    parser.add_argument(
        "command",
        nargs="?",
        default=config.CMD_STOP,
        choices=(config.CMD_FORWARD, config.CMD_LEFT, config.CMD_RIGHT, config.CMD_STOP),
        help="Command to send.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    transport = create_transport()
    try:
        print(f"Sending command {args.command} using transport={config.COMMAND_TRANSPORT}")
        transport.send(args.command)
    finally:
        transport.close()


if __name__ == "__main__":
    main()
