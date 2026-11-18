"""Read touch reports from the Waveshare board's shared I2C bus."""

from machine import Pin
from time import sleep_ms, ticks_diff, ticks_ms


class CST816S:
    ADDRESS = 0x15

    def __init__(self, bus):
        self.bus = bus
        reset = Pin(13, Pin.OUT, value=0)
        sleep_ms(5)
        reset.on()
        sleep_ms(50)
        bus.writeto_mem(self.ADDRESS, 0xFE, b"\x01")  # disable controller auto-sleep
        self.chip_id = bus.readfrom_mem(self.ADDRESS, 0xA7, 1)[0]
        bus.writeto_mem(self.ADDRESS, 0xFA, b"\x41")  # IRQ on touch
        self.pending = False
        self.last_press = None
        self.irq = Pin(5, Pin.IN, Pin.PULL_UP)
        self.irq.irq(trigger=Pin.IRQ_FALLING, handler=self._interrupt)

    def _interrupt(self, _pin):
        self.pending = True

    def read_press(self):
        if not self.pending:
            return None
        self.pending = False
        report = self.bus.readfrom_mem(self.ADDRESS, 0x02, 5)
        if report[0] & 0x0F != 1:
            return None
        now = ticks_ms()
        if self.last_press is not None and ticks_diff(now, self.last_press) < 350:
            return None
        x = ((report[1] & 0x0F) << 8) | report[2]
        y = ((report[3] & 0x0F) << 8) | report[4]
        if x < 240 and y < 240:
            self.last_press = now
            return x, y
