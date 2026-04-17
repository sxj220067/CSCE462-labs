import os
import time

import cv2

import config
from camera import create_capture, read_frame, release_capture


WINDOW_NAME = "AutoTrashCan Camera View"


def enhance_preview(frame):
    if not config.CAMERA_VIEW_SHARPEN:
        return frame

    blurred = cv2.GaussianBlur(frame, (0, 0), config.CAMERA_VIEW_SHARPEN_SIGMA)
    sharpened = cv2.addWeighted(
        frame,
        1.0 + config.CAMERA_VIEW_SHARPEN_AMOUNT,
        blurred,
        -config.CAMERA_VIEW_SHARPEN_AMOUNT,
        0,
    )
    return sharpened


def draw_overlay(frame, fps):
    frame_height, frame_width = frame.shape[:2]
    center_x = frame_width // 2
    center_y = frame_height // 2

    cv2.line(frame, (center_x, 0), (center_x, frame_height), (0, 255, 0), 1)
    cv2.line(frame, (0, center_y), (frame_width, center_y), (0, 255, 0), 1)
    cv2.circle(frame, (center_x, center_y), config.OVERHEAD_CENTER_RADIUS_PX, (255, 255, 255), 1)
    cv2.putText(
        frame,
        f"FPS: {fps:.1f}",
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 255),
        2,
    )
    cv2.putText(
        frame,
        "Press q or Esc to quit",
        (10, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
    )


def main():
    cap = create_capture()
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    window_enabled = config.SHOW_WINDOW and has_display

    if not window_enabled:
        print(
            "No graphical display detected. Set SHOW_WINDOW = True and run from a desktop session "
            "to see the live camera window."
        )

    print(
        f"Camera view starting: backend={config.CAMERA_BACKEND}, "
        f"camera={config.CAMERA_MODEL}, capture={config.CAMERA_CAPTURE_WIDTH}x{config.CAMERA_CAPTURE_HEIGHT}"
    )

    last_time = time.time()
    frame_count = 0
    fps = 0.0

    try:
        while True:
            frame = read_frame(cap, resize=False)
            if frame is None:
                print("Warning: empty frame from camera")
                continue

            frame = enhance_preview(frame)
            if (
                frame.shape[1] != config.CAMERA_VIEW_WIDTH
                or frame.shape[0] != config.CAMERA_VIEW_HEIGHT
            ):
                frame = cv2.resize(frame, (config.CAMERA_VIEW_WIDTH, config.CAMERA_VIEW_HEIGHT))

            now = time.time()
            frame_count += 1
            if now - last_time >= 1.0:
                fps = frame_count / (now - last_time)
                frame_count = 0
                last_time = now

            draw_overlay(frame, fps)

            if window_enabled:
                cv2.imshow(WINDOW_NAME, frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    break
            else:
                time.sleep(0.05)

    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        release_capture(cap)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
