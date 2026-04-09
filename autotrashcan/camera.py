import cv2
import config


def create_capture():
    cap = cv2.VideoCapture(config.CAMERA_SOURCE)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, config.TARGET_FPS)

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera source {config.CAMERA_SOURCE}")

    return cap


def read_frame(cap):
    ret, frame = cap.read()
    if not ret or frame is None:
        return None

    if frame.shape[1] != config.FRAME_WIDTH or frame.shape[0] != config.FRAME_HEIGHT:
        frame = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))

    return frame


def release_capture(cap):
    if cap is not None:
        cap.release()
