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
    # Pink/magenta front marker. Tuned around measured HSV H=134 S=170 V=217.
    ((125, 80, 120), (150, 255, 255)),
)
BACK_MARKER_HSV_RANGES = (
    # Orange back marker. Measure with camera_detection_test.py and tighten if needed.
    ((5, 80, 80), (22, 255, 255)),
)
TARGET_HSV_RANGES = (
    # Yellow target object. Keep this distinct from the orange back marker.
    ((22, 70, 70), (42, 255, 255)),
)

# Target lock behavior
LOCK_ON_FIRST_TARGET = True
LOCK_MAX_JUMP_PX = 90
LOCK_MAX_MISSED_FRAMES = 12

# Motion/controller behavior
HEADING_ALIGNMENT_DEG = 12.0
DISTANCE_STOP_PX = 55.0
FORWARD_ONLY_WHEN_ALIGNED = True
COMMAND_UPDATE_INTERVAL_S = 0.10

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
