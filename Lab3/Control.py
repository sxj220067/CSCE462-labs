#!/usr/bin/env python3
import time
import spidev
import RPi.GPIO as GPIO

CS_GPIO = 22       # MCP3008 CS -> GPIO22 (BCM)
VREF = 3.3         # MCP3008 VREF -> 3.3V
SPI_BUS = 0
SPI_DEVICE = 0
SPI_SPEED_HZ = 1_000_000

def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(CS_GPIO, GPIO.OUT, initial=GPIO.HIGH)

    spi = spidev.SpiDev()
    spi.open(SPI_BUS, SPI_DEVICE)
    spi.max_speed_hz = SPI_SPEED_HZ
    spi.mode = 0b00
    return spi

def read_ch0(spi) -> int:
    # MCP3008 read sequence for CH0, single-ended:
    # [0x01, 0x80, 0x00]
    GPIO.output(CS_GPIO, GPIO.LOW)
    resp = spi.xfer2([0x01, 0x80, 0x00])
    GPIO.output(CS_GPIO, GPIO.HIGH)

    adc = ((resp[1] & 0x03) << 8) | resp[2]   # 0..1023
    return adc

def to_volts(adc: int) -> float:
    return (adc / 1023.0) * VREF

def main():
    spi = setup()
    try:
        while True:
            adc = read_ch0(spi)
            v = to_volts(adc)
            print(f"CH0 ADC = {adc:4d}   Voltage = {v:.3f} V")
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        spi.close()
        GPIO.cleanup()

if __name__ == "__main__":
    main()