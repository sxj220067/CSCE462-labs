import os
import time
import cv2

import config
from camera import create_capture, read_frame, release_capture
from control_interface import compute_move_command, send_motor_command, STOP
from detection import MotionDetector
from prediction import predict_landing_point
from tracking import ObjectTracker, TrackState


def draw_status(frame, text, fps):
    cv2.putText(frame, f"Status: {text}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)


def draw_tracking(frame, tracker, predicted_point):
    if tracker.get_last_bbox() is not None:
        x, y, w, h = tracker.get_last_bbox()
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 128, 255), 2)

    path = tracker.get_path()
    for pt in path:
        cv2.circle(frame, pt, 3, (0, 255, 255), -1)

    if predicted_point is not None:
        cv2.circle(frame, predicted_point, 8, (0, 0, 255), 2)
        cv2.putText(
            frame,
            "Pred",
            (predicted_point[0] + 8, predicted_point[1] - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2,
        )


def main():
    cap = create_capture()
    detector = MotionDetector()
    tracker = ObjectTracker()
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    window_enabled = config.SHOW_WINDOW and has_display

    if config.SHOW_WINDOW and not has_display:
        print(
            "No graphical display detected. Continuing without a preview window. "
            "Set SHOW_WINDOW = False in config.py to suppress this message."
        )

    last_time = time.time()
    fps = 0.0
    frame_count = 0

    try:
        while True:
            frame = read_frame(cap)
            if frame is None:
                print("Warning: empty frame from camera")
                continue

            motion_mask, thresh_mask, candidates = detector.detect(frame)
            state = tracker.get_state()

            if candidates:
                _, best_bbox = candidates[0]
                tracker.update(best_bbox)
                state = tracker.get_state()
            else:
                tracker.update(None)
                state = tracker.get_state()

            predicted_point = None
            command = STOP
            offset = 0

            if state == TrackState.TRACKING and len(tracker.get_path()) >= config.MIN_TRACK_POINTS:
                predicted_point = predict_landing_point(
                    tracker.get_path(), config.FRAME_HEIGHT, config.FRAME_WIDTH, config.TARGET_FPS
                )
                if predicted_point is not None:
                    command, offset = compute_move_command(predicted_point[0], config.FRAME_WIDTH)
                    send_motor_command(command, offset)
            elif state == TrackState.LOST:
                command = STOP
                send_motor_command(command, 0)

            now = time.time()
            frame_count += 1
            if now - last_time >= 1.0:
                fps = frame_count / (now - last_time)
                frame_count = 0
                last_time = now

            if config.DEBUG_DRAW:
                draw_tracking(frame, tracker, predicted_point)
                draw_status(frame, state.name, fps)
                cv2.line(
                    frame,
                    (0, int(config.FRAME_HEIGHT * config.GROUND_LINE_RATIO)),
                    (config.FRAME_WIDTH, int(config.FRAME_HEIGHT * config.GROUND_LINE_RATIO)),
                    (128, 128, 128),
                    2,
                )

            if window_enabled:
                try:
                    cv2.imshow(config.WINDOW_NAME, frame)
                except cv2.error:
                    window_enabled = False
                    print(
                        "OpenCV display is unavailable. Continuing without a preview window. "
                        "Set SHOW_WINDOW = False in config.py to suppress this message."
                    )

            key = cv2.waitKey(1) & 0xFF if window_enabled else -1
            if key == ord('q') or key == 27:
                break

    except KeyboardInterrupt:
        print("Interrupted by user")

    finally:
        release_capture(cap)
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
