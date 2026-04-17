import cv2
import time
import config


class PiCameraCapture:
    def __init__(self, camera):
        self.camera = camera

    def read(self):
        frame = self.camera.capture_array()
        if frame is None:
            return False, None
        return True, frame

    def release(self):
        self.camera.stop()


def create_picamera2_capture():
    try:
        from picamera2 import Picamera2
    except ImportError as exc:
        raise RuntimeError(
            "Picamera2 is not installed. On Raspberry Pi OS, run: "
            "sudo apt install -y python3-picamera2"
        ) from exc

    camera_info = Picamera2.global_camera_info()
    if not camera_info:
        raise RuntimeError(
            "No Raspberry Pi cameras detected. Check the ribbon cable, camera overlay, "
            "and verify detection with: rpicam-hello --list-cameras"
        )

    camera = Picamera2()
    preview_config = camera.create_preview_configuration(
        main={"size": (config.CAMERA_CAPTURE_WIDTH, config.CAMERA_CAPTURE_HEIGHT), "format": "BGR888"},
        controls={"FrameDurationLimits": (int(1_000_000 / config.TARGET_FPS), int(1_000_000 / config.TARGET_FPS))},
    )
    camera.configure(preview_config)
    camera.start()
    time.sleep(0.2)
    return PiCameraCapture(camera)


def create_opencv_capture():
    cap = cv2.VideoCapture(config.CAMERA_SOURCE)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_CAPTURE_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_CAPTURE_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, config.TARGET_FPS)

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera source {config.CAMERA_SOURCE}")

    return cap


def create_capture():
    backend = config.CAMERA_BACKEND.lower()

    if backend == "picamera2":
        return create_picamera2_capture()

    if backend == "opencv":
        return create_opencv_capture()

    if backend == "auto":
        try:
            return create_picamera2_capture()
        except Exception as picam_error:
            print(f"Picamera2 unavailable, falling back to OpenCV: {picam_error}")
            return create_opencv_capture()

    raise RuntimeError(f"Unsupported CAMERA_BACKEND: {config.CAMERA_BACKEND}")


def read_frame(cap, resize=True):
    ret, frame = cap.read()
    if not ret or frame is None:
        return None

    if resize and (frame.shape[1] != config.FRAME_WIDTH or frame.shape[0] != config.FRAME_HEIGHT):
        frame = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))

    return frame


def release_capture(cap):
    if cap is not None:
        cap.release()
