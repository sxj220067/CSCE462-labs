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

# visual / behavior flags
DEBUG_DRAW = True
SHOW_FPS = True
SHOW_WINDOW = True

# convenience
WINDOW_NAME = "AutoTrashCan Vision"
