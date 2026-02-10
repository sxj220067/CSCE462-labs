import RPi.GPIO as GPIO
import time

from sin_wave import sin_wave
from triangle import triangle_wave
from square import square_wave

BUTTON_PIN = 17  # BCM GPIO17 (physical pin 11)

# ----------------------------
# GPIO setup (PULL-DOWN)
# ----------------------------
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def wait_for_button():
    # silent idle until pressed (pressed = HIGH)
    while GPIO.input(BUTTON_PIN) == GPIO.LOW:
        time.sleep(0.01)
    time.sleep(0.2)  # debounce

def button_pressed():
    # pressed = HIGH (pull-down wiring)
    return GPIO.input(BUTTON_PIN) == GPIO.HIGH

def get_user_inputs():
    while True:
        shape = input("Enter waveform shape (sin, triangle, square): ").strip().lower()
        if shape in ("sin", "triangle", "square"):
            break
        print("Invalid shape.")

    while True:
        try:
            freq = float(input("Enter frequency (0–50 Hz): "))
            if 0 < freq <= 50:
                break
        except ValueError:
            pass
        print("Invalid frequency.")

    while True:
        try:
            vmax = float(input("Enter max output voltage (0–VCC): "))
            break
        except ValueError:
            print("Invalid voltage.")

    return shape, freq, vmax

# ----------------------------
# Main loop
# ----------------------------
try:
    while True:
        # Requirement: display nothing until button is pressed
        wait_for_button()

        shape, freq, vmax = get_user_inputs()

        # Run waveform until button is pressed again
        if shape == "sin":
            sin_wave(freq, vmax, button_pressed)
        elif shape == "triangle":
            triangle_wave(freq, vmax, button_pressed)
        else:
            square_wave(freq, vmax, button_pressed)

finally:
    GPIO.cleanup()