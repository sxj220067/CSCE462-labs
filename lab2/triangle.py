def triangle_wave():
    t = 0.0
    tStep = 0.01

    while True:
        # Triangle wave between -1 and +1
        phase = t % 2.0
        if phase < 1.0:
            tri = phase          # rising 0 → 1
        else:
            tri = 2.0 - phase    # falling 1 → 0

        tri = 2.0 * tri - 1.0     # scale to -1 → +1

        voltage = 2048 * (1.0 + 0.5 * tri)
        dac.set_voltage(int(voltage))

        t += tStep
        time.sleep(0.0005)
        
