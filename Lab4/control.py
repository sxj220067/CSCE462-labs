# lab4_step_counter.py
# CSCE 462 - Lab 4: MPU6050 IMU raw read + real-time step counting
# Requires:
#   sudo pip3 install adafruit-circuitpython-mpu6050
# Run:
#   python3 lab4_step_counter.py

import board
import busio
import adafruit_mpu6050
from time import perf_counter, sleep
from math import sqrt


# User-tunable parameters

PRINT_EVERY_SEC = 0.20    
ALPHA = 0.15             
REFRACTORY_SEC = 0.30   

# Peak detection thresholds (tune for your sensor placement)
# We'll detect peaks on "dynamic magnitude" = |a| - baseline(gravity-ish)
# Start with these, then tune while watching the debug values.
THRESH_HIGH = 1.25        
THRESH_LOW  = 0.55       


# Setup IMU
i2c = busio.I2C(board.SCL, board.SDA)
mpu = adafruit_mpu6050.MPU6050(i2c)


# Helpers
def lpf(prev, x, alpha):
    return prev + alpha * (x - prev)


# Main loop state
t_last = perf_counter()
t_last_print = t_last
t_last_step = -1e9

# Filtered acceleration components
fax = fay = faz = 0.0

# Baseline magnitude (captures gravity + slow drift)
base_mag = 9.8

# Step detection state machine
armed = True  

steps = 0

print("Starting MPU6050 read + step counting...")
print("Tip: Hold the sensor steady against your body (pocket/hand/chest) while walking.\n")

while True:
    now = perf_counter()
    dt = now - t_last
    t_last = now

    ax, ay, az = mpu.acceleration   
    gx, gy, gz = mpu.gyro          

    # Low-pass filter accel components
    fax = lpf(fax, ax, ALPHA)
    fay = lpf(fay, ay, ALPHA)
    faz = lpf(faz, az, ALPHA)

    # Magnitude of filtered acceleration
    mag = sqrt(fax*fax + fay*fay + faz*faz)

    # Baseline gravity estimate (very slow low-pass)
    base_mag = lpf(base_mag, mag, 0.01)

    # Dynamic component (removes gravity-ish part)
    dyn = mag - base_mag


    # Step detection (peak + hysteresis + refractory)

    # Logic:
    if armed:
        if dyn > THRESH_HIGH and (now - t_last_step) > REFRACTORY_SEC:
            steps += 1
            t_last_step = now
            armed = False
    else:
        if dyn < THRESH_LOW:
            armed = True


    # Print status periodically
    if (now - t_last_print) >= PRINT_EVERY_SEC:
        t_last_print = now
        print(
            f"steps={steps:3d} | "
            f"acc(m/s^2)=({ax:+6.2f},{ay:+6.2f},{az:+6.2f}) | "
            f"|a|={mag:5.2f} base={base_mag:5.2f} dyn={dyn:+5.2f} | "
            f"gyro=({gx:+6.2f},{gy:+6.2f},{gz:+6.2f})"
        )

    # Small sleep to reduce CPU load (still plenty fast for walking)
    sleep(0.005)