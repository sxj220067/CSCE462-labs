

def sin_wave():
    t =0.0
    tStep =0.05

    while True:
        voltage = 2048*(1.0+0.5*math.sin(6.2832*t))
    dac.set_voltage(int(voltage))
    t += tStep
    time.sleep(0.0005)
 