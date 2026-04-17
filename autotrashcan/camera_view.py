import os
import time

import cv2

import config
from camera import create_capture, read_frame, release_capture


WINDOW_NAME = "AutoTrashCan Camera View"


def draw_overlay(frame, fps):
    center_x = config.FRAME_WIDTH // 2
    center_y = config.FRAME_HEIGHT // 2

    cv2.line(frame, (center_x, 0), (center_x, config.FRAME_HEIGHT), (0, 255, 0), 1)
    cv2.line(frame, (0, center_y), (config.FRAME_WIDTH, center_y), (0, 255, 0), 1)
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
        f"resolution={config.FRAME_WIDTH}x{config.FRAME_HEIGHT}"
    )

    last_time = time.time()
    frame_count = 0
    fps = 0.0

    try:
        while True:
            frame = read_frame(cap)
            if frame is None:
                print("Warning: empty frame from camera")
                continue

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
