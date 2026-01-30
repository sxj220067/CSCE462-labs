def square_wave():
    t = 0.0
    tStep = 0.01

    while True:
        # Square wave: +1 for first half of cycle, -1 for second half
        phase = t % 1.0
        if phase < 0.5:
            sq = 1.0      # high
        else:
            sq = -1.0     # low

        voltage = 2048 * (1.0 + 0.5 * sq)
        dac.set_voltage(int(voltage))

        t += tStep
        time.sleep(0.0005)
