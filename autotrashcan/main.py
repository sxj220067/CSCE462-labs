import os
import time
import cv2

import config
from camera import create_capture, read_frame, release_capture
from control_interface import compute_approach_command, send_motor_command, STOP
from detection import MotionDetector
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
            "Aim",
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
    last_status_print = time.time()

    if config.SHOW_WINDOW and not has_display:
        print(
            "No graphical display detected. Continuing without a preview window. "
            "Set SHOW_WINDOW = False in config.py to suppress this message."
        )

    print(
        f"AutoTrashCan starting: backend={config.CAMERA_BACKEND}, "
        f"window={'on' if window_enabled else 'off'}, motor_mock={config.MOTOR_MOCK}"
    )

    last_time = time.time()
    fps = 0.0
    frame_count = 0
    last_command = STOP
    last_offset = 0
    last_turn_strength = 0.0
    last_command_sent_time = 0.0
    command_hold_frames = 0

    try:
        while True:
            frame = read_frame(cap)
            if frame is None:
                print("Warning: empty frame from camera")
                continue

            motion_mask, thresh_mask, candidates = detector.detect(frame)
            state = tracker.get_state()

            if candidates:
                best_bbox = tracker.select_best_candidate(candidates)
                tracker.update(best_bbox)
                state = tracker.get_state()
            else:
                tracker.update(None)
                state = tracker.get_state()

            aim_point = None
            command = STOP
            offset = 0
            turn_strength = 0.0

            if state == TrackState.TRACKING and tracker.get_last_bbox() is not None:
                last_bbox = tracker.get_last_bbox()
                x, y, w, h = last_bbox
                target_center = (int(x + w / 2), int(y + h / 2))
                aim_point = target_center
                command, offset, turn_strength = compute_approach_command(
                    last_bbox,
                    config.FRAME_WIDTH,
                    config.FRAME_HEIGHT,
                )
                command_hold_frames = config.COMMAND_HOLD_FRAMES
            elif state == TrackState.LOST:
                command = STOP
                command_hold_frames = 0

            if command == STOP and command_hold_frames > 0 and last_command != STOP:
                command = last_command
                offset = last_offset
                turn_strength = last_turn_strength
                command_hold_frames -= 1

            now = time.time()

            should_send_command = (
                command != last_command
                or abs(offset - last_offset) > config.CENTER_DEADZONE_PX
                or abs(turn_strength - last_turn_strength) >= 0.1
                or (now - last_command_sent_time) >= config.COMMAND_UPDATE_INTERVAL_S
            )

            if should_send_command:
                send_motor_command(command, offset, turn_strength)
                last_command = command
                last_offset = offset
                last_turn_strength = turn_strength
                last_command_sent_time = now

            frame_count += 1
            if now - last_time >= 1.0:
                fps = frame_count / (now - last_time)
                frame_count = 0
                last_time = now

            if now - last_status_print >= config.STATUS_PRINT_INTERVAL:
                print(
                    f"[STATUS] state={state.name} fps={fps:.1f} "
                    f"candidates={tracker.candidate_count} tracked_points={len(tracker.get_path())} "
                    f"locked={tracker.is_locked()} cooldown={tracker.reacquire_cooldown} "
                    f"command={command} strength={turn_strength:.2f}"
                )
                last_status_print = now

            if config.DEBUG_DRAW:
                draw_tracking(frame, tracker, aim_point)
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
