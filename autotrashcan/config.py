# Configuration parameters for auto trash can vision pipeline

# camera settings
CAMERA_BACKEND = "picamera2"  # "auto", "opencv", or "picamera2"
CAMERA_SOURCE = 0  # camera index for USB/Webcam when using the OpenCV backend
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
TARGET_FPS = 30

# motion detector settings
MOG_HISTORY = 120
MOG_VAR_THRESHOLD = 40
MOG_DETECT_SHADOWS = False
MOG_LEARNING_RATE = 0.03
BLUR_SIZE = (7, 7)
THRESHOLD_VALUE = 45
MORPH_KERNEL = (5, 5)
MIN_CONTOUR_AREA = 900
MAX_CONTOUR_AREA = 35000
ASPECT_RATIO_MIN = 0.3
ASPECT_RATIO_MAX = 2.5
MAX_CANDIDATES = 4
SEARCH_TOP_RATIO = 0.05
SEARCH_BOTTOM_RATIO = 0.88
EDGE_IGNORE_PX = 20

# tracking settings
TRACK_HISTORY = 20
TRACK_LOST_MAX_FRAMES = 4
MIN_TRACK_POINTS = 3
MAX_TRACK_JUMP_PX = 180
TARGET_LOCK_BONUS = 2500.0

# prediction settings
GRAVITY_PX_PER_S2 = 4000.0
GROUND_LINE_RATIO = 0.94
MIN_PREDICT_TIME = 0.10
MAX_PREDICT_TIME = 1.0
MIN_DOWNWARD_VELOCITY_PX_PER_S = 60.0

# control settings
CENTER_DEADZONE_PX = 24
MOVE_SCALE = 1.0  # scalar for speed command
MOTOR_MOCK = False
MOTOR_DRIVER = "l298n"
L298N_LEFT_ENABLE_PIN = 13
L298N_LEFT_IN1_PIN = 5
L298N_LEFT_IN2_PIN = 6
L298N_RIGHT_ENABLE_PIN = 18
L298N_RIGHT_IN3_PIN = 23
L298N_RIGHT_IN4_PIN = 24
L298N_PWM_FREQUENCY = 1000
MOTOR_FORWARD_DUTY = 0.95
MOTOR_TURN_DUTY = 0.85
LEFT_MOTOR_SCALE = 1.0
RIGHT_MOTOR_SCALE = 1.0
# Motor tuning notes for real hardware:
# - Increase MOTOR_FORWARD_DUTY if the robot does not move or feels too slow.
# - Decrease MOTOR_FORWARD_DUTY if the robot moves too fast or overshoots.
# - Increase MOTOR_TURN_DUTY if turns are too weak or too slow.
# - Decrease MOTOR_TURN_DUTY if turns are too sharp, jerky, or unstable.
# - Reduce LEFT_MOTOR_SCALE or RIGHT_MOTOR_SCALE if one side consistently runs faster.
# - Set LEFT_MOTOR_INVERTED or RIGHT_MOTOR_INVERTED to True if that side spins backward when forward is expected.
# This project does not use a separate motor calibration file; these config values are the main adjustment points.
LEFT_MOTOR_INVERTED = False
RIGHT_MOTOR_INVERTED = True

# visual / behavior flags
DEBUG_DRAW = True
SHOW_FPS = True
SHOW_WINDOW = True
STATUS_PRINT_INTERVAL = 1.0

# convenience
WINDOW_NAME = "AutoTrashCan Vision"
