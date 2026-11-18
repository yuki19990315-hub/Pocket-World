"""Motion reactions are visual-only: no accidental world state mutation."""


def _clamp(v):
    return max(-1.0, min(1.0, v))


class MotionEffects:
    def __init__(self, shake_enabled=False):
        self.shake_enabled = bool(shake_enabled)
        self.tilt_x = 0.0
        self.tilt_y = 0.0
        self.shake_id = 0
        self.last_shake_ms = None
        self.connected = False

    def observe(self, acceleration, angular_rate, now_ms):
        if len(acceleration) != 3 or len(angular_rate) != 3:
            raise ValueError("3-axis accel and gyro required")
        x, y, z = (float(value) for value in acceleration)
        gx, gy, gz = (float(value) for value in angular_rate)
        self.connected = True
        # The accelerometer determines gravity; gyro identifies fast movement.
        # Keep effects modest so the screen stays legible on a desk.
        self.tilt_x = 0.75 * self.tilt_x + 0.25 * _clamp(x / 0.8)
        self.tilt_y = 0.75 * self.tilt_y + 0.25 * _clamp(y / 0.8)
        if abs(self.tilt_x) < 0.03:
            self.tilt_x = 0.0
        if abs(self.tilt_y) < 0.03:
            self.tilt_y = 0.0
        # A large acceleration impulse or rapid rotation can be a shake.
        mag = (x * x + y * y + z * z) ** 0.5
        rotation = (gx * gx + gy * gy + gz * gz) ** 0.5
        shaking = abs(mag - 1.0) > 0.8 or rotation > 270
        if (self.shake_enabled and shaking and
            (self.last_shake_ms is None or now_ms - self.last_shake_ms >= 15000)):
            self.shake_id += 1
            self.last_shake_ms = now_ms
        return self.snapshot()

    def snapshot(self):
        return {"connected": self.connected, "tilt_x": round(self.tilt_x, 3),
                "tilt_y": round(self.tilt_y, 3), "shake_id": self.shake_id,
                "shake_enabled": self.shake_enabled}
