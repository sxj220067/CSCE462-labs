# Configuration parameters for auto trash can vision pipeline

# camera settings
CAMERA_BACKEND = "picamera2"  # "auto", "opencv", or "picamera2"
CAMERA_SOURCE = 0  # camera index for USB/Webcam when using the OpenCV backend
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
TARGET_FPS = 20

# motion detector settings
MOG_HISTORY = 200
MOG_VAR_THRESHOLD = 25
MOG_DETECT_SHADOWS = True
BLUR_SIZE = (7, 7)
THRESHOLD_VALUE = 30
MORPH_KERNEL = (5, 5)
MIN_CONTOUR_AREA = 600
MAX_CONTOUR_AREA = 35000
ASPECT_RATIO_MIN = 0.3
ASPECT_RATIO_MAX = 2.5
MAX_CANDIDATES = 4

# tracking settings
TRACK_HISTORY = 20
TRACK_LOST_MAX_FRAMES = 8
MIN_TRACK_POINTS = 4

# prediction settings
GRAVITY_PX_PER_S2 = 4000.0
GROUND_LINE_RATIO = 0.94
MIN_PREDICT_TIME = 0.10
MAX_PREDICT_TIME = 2.2

# control settings
CENTER_DEADZONE_PX = 40
MOVE_SCALE = 1.0  # scalar for speed command
MOTOR_MOCK = True
MOTOR_DRIVER = "l298n"
L298N_LEFT_ENABLE_PIN = 18
L298N_LEFT_IN1_PIN = 23
L298N_LEFT_IN2_PIN = 24
L298N_RIGHT_ENABLE_PIN = 13
L298N_RIGHT_IN3_PIN = 5
L298N_RIGHT_IN4_PIN = 6
L298N_PWM_FREQUENCY = 1000
MOTOR_FORWARD_DUTY = 0.65
MOTOR_TURN_DUTY = 0.55
# Motor tuning notes for real hardware:
# - Increase MOTOR_FORWARD_DUTY if the robot does not move or feels too slow.
# - Decrease MOTOR_FORWARD_DUTY if the robot moves too fast or overshoots.
# - Increase MOTOR_TURN_DUTY if turns are too weak or too slow.
# - Decrease MOTOR_TURN_DUTY if turns are too sharp, jerky, or unstable.
# - Set LEFT_MOTOR_INVERTED or RIGHT_MOTOR_INVERTED to True if that side spins backward when forward is expected.
# This project does not use a separate motor calibration file; these config values are the main adjustment points.
LEFT_MOTOR_INVERTED = False
RIGHT_MOTOR_INVERTED = False

# visual / behavior flags
DEBUG_DRAW = True
SHOW_FPS = True
SHOW_WINDOW = True
STATUS_PRINT_INTERVAL = 1.0

# convenience
WINDOW_NAME = "AutoTrashCan Vision"
