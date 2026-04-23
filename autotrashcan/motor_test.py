import time

import config
from control_interface import L298NMotorController


STEP_SECONDS = 0.2


def print_menu():
    print()
    print("Motor test commands:")
    print("  lf   -> left motor forward")
    print("  lr   -> left motor reverse")
    print("  rf   -> right motor forward")
    print("  rr   -> right motor reverse")
    print("  bf   -> both motors forward")
    print("  br   -> both motors reverse")
    print("  sl   -> spin left")
    print("  sr   -> spin right")
    print("  stop -> stop motors")
    print("  q    -> quit")
    print()


def run_command(motor, command):
    if command == "lf":
        print("Output: left motor forward")
        motor._drive(True, True, config.MOTOR_FORWARD_DUTY, 0.0)
    elif command == "lr":
        print("Output: left motor reverse")
        motor._drive(False, True, config.MOTOR_FORWARD_DUTY, 0.0)
    elif command == "rf":
        print("Output: right motor forward")
        motor._drive(True, True, 0.0, config.MOTOR_FORWARD_DUTY)
    elif command == "rr":
        print("Output: right motor reverse")
        motor._drive(True, False, 0.0, config.MOTOR_FORWARD_DUTY)
    elif command == "bf":
        print("Output: both motors forward")
        motor.move_forward()
    elif command == "br":
        print("Output: both motors reverse")
        motor._drive(False, False, config.MOTOR_REVERSE_DUTY, config.MOTOR_REVERSE_DUTY)
    elif command == "sl":
        print("Output: spin left")
        motor.move_left()
    elif command == "sr":
        print("Output: spin right")
        motor.move_right()
    elif command == "stop":
        print("Output: stop")
        motor.stop()
    else:
        print("Unknown command. Type one of: lf lr rf rr bf br sl sr stop q")
        return

    if command != "stop":
        time.sleep(STEP_SECONDS)
        motor.stop()
        print("Output: stop")


def main():
    if config.MOTOR_MOCK:
        print("Set MOTOR_MOCK = False in config.py before using motor_test.py.")
        return

    print("Interactive motor test starting.")
    print("Lift the wheels off the ground before sending commands.")
    print_menu()

    motor = L298NMotorController()

    try:
        motor.stop()
        while True:
            user_input = input("Enter motor command: ").strip().lower()
            if user_input in {"q", "quit", "exit"}:
                print("Exiting motor test.")
                break
            run_command(motor, user_input)
    finally:
        motor.close()


if __name__ == "__main__":
    main()
