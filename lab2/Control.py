import RPi.GPIO as GPIO
import time

from sin_wave import sin_wave
from triangle import triangle_wave
from square import square_wave

BUTTON_PIN = 17   # change to your wiring

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

def wait_for_button():
    print("Waiting for button press...")
    GPIO.wait_for_edge(BUTTON_PIN, GPIO.RISING)
    time.sleep(0.05)   # debounce

def get_user_inputs():
    shape = input("Enter waveform shape (sin, triangle, square): ").strip().lower()
    freq = float(input("Enter frequency (0–50 Hz): "))
    vmax = float(input("Enter max output voltage (0–VCC): "))
    return shape, freq, vmax

while True:
    wait_for_button()
    shape, freq, vmax = get_user_inputs()

    if shape == "sin":
        sin_wave(freq, vmax)
    elif shape == "triangle":
        triangle_wave(freq, vmax)
    elif shape == "square":
        square_wave(freq, vmax)
    else:
        print("Invalid shape")
