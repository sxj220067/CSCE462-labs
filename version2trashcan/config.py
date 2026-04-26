# Fixed-camera trash can configuration.

# Camera
CAMERA_BACKEND = "auto"  # "auto", "opencv", or "picamera2"
CAMERA_SOURCE = 0
CAMERA_CAPTURE_WIDTH = 960
CAMERA_CAPTURE_HEIGHT = 540
FRAME_WIDTH = 640
FRAME_HEIGHT = 360
TARGET_FPS = 30
CAMERA_COLOR_MODE = "bgr"  # "bgr" or "rgb_to_bgr"
SHOW_WINDOW = True
WINDOW_NAME = "Version2TrashCan"
STATUS_PRINT_INTERVAL = 1.0

# Marker and target detection
BLUR_SIZE = (5, 5)
MORPH_KERNEL = (5, 5)
MARKER_DILATE_ITERATIONS = 2
MIN_MARKER_AREA = 120
MAX_MARKER_AREA = 20000
MIN_TARGET_AREA = 180
MAX_TARGET_AREA = 35000

# HSV ranges are in OpenCV format: H in [0,179], S/V in [0,255].
# Adjust these for your real lighting and tape/object colors.
FRONT_MARKER_HSV_RANGES = (
    # Pink/magenta front marker. Tuned around measured HSV H=142 S=231 V=254.
    ((132, 150, 180), (152, 255, 255)),
)
BACK_MARKER_HSV_RANGES = (
    # Green back marker. Tuned around measured HSV H=61 S=80 V=252.
    ((52, 45, 190), (70, 140, 255)),
)
TARGET_HSV_RANGES = (
    # Tennis ball target. Tuned around measured HSV H=88 S=80 V=240.
    ((80, 45, 190), (98, 140, 255)),
)

# Target lock behavior
LOCK_ON_FIRST_TARGET = True
LOCK_MAX_JUMP_PX = 90
LOCK_MAX_MISSED_FRAMES = 12
TARGET_COLLECTED_DISTANCE_PX = 45.0
TARGET_COLLECTED_SECONDS = 2.0
RETURN_HOME_WHEN_TARGET_COLLECTED = True
RETURN_HOME_WHEN_TARGET_LOST = True
HOME_STOP_PX = 45.0

# Motion/controller behavior
HEADING_ALIGNMENT_DEG = 22.0
FULL_TURN_ANGLE_DEG = 90.0
TURN_STRENGTH_SCALE = 0.70
MIN_TURN_STRENGTH = 20
MAX_TURN_STRENGTH = 75
DISTANCE_STOP_PX = 55.0
FORWARD_ONLY_WHEN_ALIGNED = True
COMMAND_UPDATE_INTERVAL_S = 0.20
COMMAND_CHANGE_CONFIRMATIONS = 3
SWAP_TURN_COMMANDS = True

# Command transport to ESP32
COMMAND_TRANSPORT = "bluetooth"  # "stdout", "serial", or "bluetooth"
SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_BAUDRATE = 9600
SERIAL_TIMEOUT_S = 0.25
BLUETOOTH_DEVICE_NAME = "Version2TrashCan"
BLUETOOTH_MAC_ADDRESS = "D0:EF:76:44:84:52"
BLUETOOTH_CHANNEL = 1
BLUETOOTH_CONNECT_TIMEOUT_S = 8.0

# Supported commands
CMD_FORWARD = "F"
CMD_LEFT = "L"
CMD_RIGHT = "R"
CMD_STOP = "S"
