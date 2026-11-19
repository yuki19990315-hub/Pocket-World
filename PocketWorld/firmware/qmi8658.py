"""Minimal MicroPython QMI8658C 6-axis reader for the Waveshare 1.28 board.

Register addresses and scaling: QST QMI8658C datasheet, registers CTRL2/3/7,
AX_L (0x35) and GX_L (0x3B).
"""


def _signed16(lo, hi):
    value = lo | (hi << 8)
    return value - 65536 if value >= 32768 else value


class QMI8658:
    def __init__(self, i2c, address=None):
        self.i2c = i2c
        possible = (address,) if address is not None else (0x6B, 0x6A)
        self.address = None
        for candidate in possible:
            try:
                if i2c.readfrom_mem(candidate, 0x00, 1)[0] == 0x05:
                    self.address = candidate
                    break
            except OSError:
                continue
        if self.address is None:
            raise OSError("QMI8658C is not responding")
        # CTRL1: enable register auto-increment and select little-endian output.
        self._write(0x02, 0x40)
        # Accel: +/-2 g, 62.5Hz; gyro: +/-512 dps, 62.5Hz.
        self._write(0x03, 0x07)
        self._write(0x04, 0x57)
        self._write(0x08, 0x03)  # aEN | gEN, no attitude engine.

    def _write(self, register, value):
        self.i2c.writeto_mem(self.address, register, bytes((value,)))

    def read(self):
        data = self.i2c.readfrom_mem(self.address, 0x35, 12)
        if len(data) != 12:
            raise OSError("Short QMI8658 sample")
        accel = tuple(_signed16(data[i], data[i + 1]) / 16384.0 for i in (0, 2, 4))
        gyro = tuple(_signed16(data[i], data[i + 1]) / 64.0 for i in (6, 8, 10))
        return accel, gyro

    def standby(self):
        self._write(0x08, 0x00)
