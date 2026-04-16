import time

import config
from control_interface import (
    MOVE_FORWARD,
    MOVE_LEFT,
    MOVE_REVERSE,
    MOVE_RIGHT,
    STOP,
    send_motor_command,
)


DEFAULT_STEP_SECONDS = 0.4


def print_menu():
    print()
    print("Manual drive commands:")
    print("  w      -> forward")
    print("  a      -> turn left")
    print("  d      -> turn right")
    print("  s      -> stop")
    print("  x      -> reverse")
    print("  q      -> quit")
    print()
    print(f"Each motion command runs for {DEFAULT_STEP_SECONDS:.1f}s, then stops.")


def drive_for(command, seconds):
    send_motor_command(command, 0)
    time.sleep(seconds)
    send_motor_command(STOP, 0)


def main():
    if config.MOTOR_MOCK:
        print("Set MOTOR_MOCK = False in config.py before using manual_drive.py.")
        return

    print("Manual drive starting.")
    print("Keep the robot on the floor only if you have clear space and can stop it quickly.")
    print_menu()

    command_map = {
        "w": MOVE_FORWARD,
        "a": MOVE_LEFT,
        "d": MOVE_RIGHT,
        "s": STOP,
        "x": MOVE_REVERSE,
    }

    while True:
        user_input = input("Enter drive command: ").strip().lower()
        if user_input in {"q", "quit", "exit"}:
            send_motor_command(STOP, 0)
            print("Exiting manual drive.")
            break

        command = command_map.get(user_input)
        if command is None:
            print("Unknown command. Use: w a d s x q")
            continue

        if command == STOP:
            send_motor_command(STOP, 0)
            print("Output: stop")
            continue

        print(f"Output: {command}")
        drive_for(command, DEFAULT_STEP_SECONDS)
        print("Output: STOP")


if __name__ == "__main__":
    main()
