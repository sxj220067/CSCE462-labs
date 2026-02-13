from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

import time

try:
    import spidev  # type: ignore
except Exception as e:
    spidev = None  # type: ignore

try:
    import RPi.GPIO as GPIO  # type: ignore
except Exception:
    GPIO = None  # type: ignore


@dataclass
class MCP3008Config:
    bus: int = 0
    device: int = 0
    max_hz: int = 1350000
    mode: int = 0

    use_gpio_cs: bool = False
    gpio_cs_pin: int = 22  # BCM numbering


class MCP3008:
    """Minimal MCP3008 driver.

    Supports:
    - Hardware chip select (CE0/CE1) via spidev.open(bus, device)
    - GPIO chip select (CS wired to a GPIO pin) using spidev.no_cs + manual GPIO toggling
    """

    def __init__(self, cfg: MCP3008Config):
        if spidev is None:
            raise RuntimeError("spidev is not installed. Run: pip3 install spidev")

        self.cfg = cfg
        self.spi = spidev.SpiDev()
        self.spi.open(cfg.bus, cfg.device)
        self.spi.max_speed_hz = cfg.max_hz
        self.spi.mode = cfg.mode

        if cfg.use_gpio_cs:
            if GPIO is None:
                raise RuntimeError("RPi.GPIO is not available. On Raspberry Pi OS: sudo apt-get install python3-rpi.gpio")
            # Use manual CS
            self.spi.no_cs = True
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(cfg.gpio_cs_pin, GPIO.OUT, initial=GPIO.HIGH)

    def close(self) -> None:
        if self.cfg.use_gpio_cs and GPIO is not None:
            try:
                GPIO.output(self.cfg.gpio_cs_pin, GPIO.HIGH)
                GPIO.cleanup(self.cfg.gpio_cs_pin)
            except Exception:
                pass
        try:
            self.spi.close()
        except Exception:
            pass

    def _cs_low(self) -> None:
        if self.cfg.use_gpio_cs and GPIO is not None:
            GPIO.output(self.cfg.gpio_cs_pin, GPIO.LOW)

    def _cs_high(self) -> None:
        if self.cfg.use_gpio_cs and GPIO is not None:
            GPIO.output(self.cfg.gpio_cs_pin, GPIO.HIGH)

    def read(self, channel: int) -> int:
        """Read 10-bit ADC value (0..1023) from channel 0..7."""
        if not (0 <= channel <= 7):
            raise ValueError("channel must be 0..7")

        # MCP3008 protocol (single-ended):
        # Start bit: 1
        # Single-ended: 1
        # Channel: 3 bits
        # We send 3 bytes and read 3 bytes back.
        #
        # Byte1: 0b00000001
        # Byte2: 0b10000000 | (channel << 4)
        # Byte3: 0b00000000
        cmd1 = 0x01
        cmd2 = 0x80 | (channel << 4)
        cmd3 = 0x00

        self._cs_low()
        resp = self.spi.xfer2([cmd1, cmd2, cmd3])
        self._cs_high()

        # resp[1] contains top 2 bits in its low bits, resp[2] has remaining 8 bits
        value = ((resp[1] & 0x03) << 8) | resp[2]
        return int(value)

    def read_voltage(self, channel: int, vref: float = 3.3) -> float:
        return self.read(channel) * (vref / 1023.0)
