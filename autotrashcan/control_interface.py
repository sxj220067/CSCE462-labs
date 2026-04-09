import config


MOVE_LEFT = "MOVE_LEFT"
MOVE_RIGHT = "MOVE_RIGHT"
MOVE_FORWARD = "MOVE_FORWARD"
STOP = "STOP"


def compute_move_command(predicted_x, frame_width, deadzone_px=config.CENTER_DEADZONE_PX):
    if predicted_x is None:
        return STOP, 0

    center_x = frame_width // 2
    offset = int(predicted_x - center_x)

    if abs(offset) <= deadzone_px:
        return MOVE_FORWARD, 0

    if offset < 0:
        return MOVE_LEFT, offset

    return MOVE_RIGHT, offset


def send_motor_command(command, offset=0):
    if config.MOTOR_MOCK:
        print(f"[MOTOR_STUB] {command} offset={offset}")
        return True

    # Replace this block with serial/ROS/pigpio/motor driver integration.
    # Example:
    # serial.write(f"{command}:{offset}\n")
    return True
