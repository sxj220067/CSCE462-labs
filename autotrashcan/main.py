import os
import time
import cv2

import config
from camera import create_capture, read_frame, release_capture
from control_interface import compute_path_command, plan_path_to_target, send_motor_command, STOP
from detection import create_detector
from prediction import predict_landing_point
from tracking import ObjectTracker, TrackState


def draw_status(frame, text, fps):
    cv2.putText(frame, f"Status: {text}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)


def draw_tracking(frame, tracker, predicted_point, planned_path, target_verified):
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

    if planned_path:
        for idx in range(len(planned_path) - 1):
            cv2.line(frame, planned_path[idx], planned_path[idx + 1], (255, 0, 255), 2)
        for point in planned_path:
            cv2.circle(frame, point, 4, (255, 0, 255), -1)

    verification_color = (0, 200, 0) if target_verified else (0, 165, 255)
    verification_text = "Target checked" if target_verified else "Checking target"
    cv2.putText(frame, verification_text, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, verification_color, 2)

    if config.CAMERA_FACING_UP:
        frame_center = (config.FRAME_WIDTH // 2, config.FRAME_HEIGHT // 2)
        cv2.circle(frame, frame_center, config.OVERHEAD_CENTER_RADIUS_PX, (255, 255, 255), 1)
        cv2.drawMarker(frame, frame_center, (255, 255, 255), cv2.MARKER_CROSS, 18, 1)


def main():
    cap = create_capture()
    detector = create_detector()
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
        f"window={'on' if window_enabled else 'off'}, motor_mock={config.MOTOR_MOCK}, "
        f"detector_mode={config.DETECTOR_MODE}"
    )

    last_time = time.time()
    fps = 0.0
    frame_count = 0
    last_command = STOP
    last_offset = 0
    last_turn_strength = 0.0
    last_command_sent_time = 0.0
    try:
        while True:
            frame = read_frame(cap)
            if frame is None:
                print("Warning: empty frame from camera")
                continue

            motion_mask, thresh_mask, candidates = detector.detect(frame)
            state = tracker.get_state()

            current_bbox = None
            if candidates:
                current_bbox = tracker.select_best_candidate(candidates)
                tracker.update(current_bbox)
                state = tracker.get_state()
            else:
                tracker.update(None)
                state = tracker.get_state()

            aim_point = None
            planned_path = []
            command = STOP
            offset = 0
            turn_strength = 0.0
            target_verified = tracker.is_target_stable()

            if current_bbox is not None:
                x, y, w, h = current_bbox
                target_center = (int(x + w / 2), int(y + h / 2))
                aim_point = target_center

                if config.USE_PREDICTION and len(tracker.get_path()) >= config.MIN_TRACK_POINTS:
                    predicted_point = predict_landing_point(
                        tracker.get_path(),
                        config.FRAME_HEIGHT,
                        config.FRAME_WIDTH,
                        fps,
                    )
                    if predicted_point is not None:
                        aim_point = predicted_point

                planned_path = plan_path_to_target(aim_point, config.FRAME_WIDTH, config.FRAME_HEIGHT)

                command, offset, turn_strength = compute_path_command(
                    planned_path,
                    config.FRAME_WIDTH,
                    config.FRAME_HEIGHT,
                    target_bbox=current_bbox,
                )
            else:
                command = STOP

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
                    f"stable={target_verified} command={command} strength={turn_strength:.2f}"
                )
                last_status_print = now

            if config.DEBUG_DRAW:
                draw_tracking(frame, tracker, aim_point, planned_path, target_verified)
                draw_status(frame, state.name, fps)
                cv2.line(
                    frame,
                    (config.FRAME_WIDTH // 2, 0),
                    (config.FRAME_WIDTH // 2, config.FRAME_HEIGHT),
                    (0, 255, 0),
                    1,
                )
                if config.CAMERA_FACING_UP:
                    cv2.line(
                        frame,
                        (0, config.FRAME_HEIGHT // 2),
                        (config.FRAME_WIDTH, config.FRAME_HEIGHT // 2),
                        (0, 255, 0),
                        1,
                    )
                else:
                    cv2.line(
                        frame,
                        (0, int(config.FRAME_HEIGHT * config.TARGET_CLOSE_Y_RATIO)),
                        (config.FRAME_WIDTH, int(config.FRAME_HEIGHT * config.TARGET_CLOSE_Y_RATIO)),
                        (0, 255, 0),
                        1,
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
