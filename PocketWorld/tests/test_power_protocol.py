import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
import main
import settings
from power_runtime import PowerRuntime
from motion_effects import MotionEffects
from work_schedule import DEFAULT_SCHEDULE
from world_model import PocketWorld


class Client:
    def __init__(self, request):
        self.request = request
        self.written = bytearray()
    def settimeout(self, timeout):
        pass
    def recv(self, size):
        chunk = self.request[:min(13, size)]
        self.request = self.request[len(chunk):]
        return chunk
    def sendall(self, value):
        self.written.extend(value)


def invoke(method, path, payload=None, key=None):
    data = json.dumps(payload).encode() if payload is not None else b""
    headers = "Content-Length: %d\r\n" % len(data)
    if key is not None:
        headers += "X-Admin-Key: %s\r\n" % key
    return Client(("%s %s HTTP/1.1\r\n%s\r\n" % (method, path, headers)).encode() + data)


def response_body(client):
    return json.loads(bytes(client.written).split(b"\r\n\r\n", 1)[1])


class TestPowerProtocol(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp.name)
        self.old_key = settings.ADMIN_KEY
        settings.ADMIN_KEY = "test-only-secret"
        self.power = PowerRuntime(False)
        self.engine = PocketWorld()

    def tearDown(self):
        settings.ADMIN_KEY = self.old_key
        os.chdir(self.old_cwd)
        self.temp.cleanup()

    def test_get_power_reports_unarmed_and_unknown_clock(self):
        client = invoke("GET", "/api/power")
        main.service(client, self.engine, self.power)
        result = response_body(client)
        self.assertFalse(result["clock_synced"])
        self.assertFalse(result["sleep_supported"])
        self.assertEqual(result["mode"], "clock_unknown")

    def test_schedule_requires_admin_key_and_valid_clock(self):
        payload = {"clock": 1790000000, "schedule": dict(DEFAULT_SCHEDULE, enabled=True)}
        client = invoke("POST", "/api/power/schedule", payload)
        main.service(client, self.engine, self.power)
        self.assertIn(b"403 Forbidden", client.written)
        self.assertFalse(os.path.exists("power.json"))

        payload["clock"] = 5
        client = invoke("POST", "/api/power/schedule", payload, key="test-only-secret")
        main.service(client, self.engine, self.power)
        self.assertIn(b"400 Bad Request", client.written)
        self.assertFalse(os.path.exists("power.json"))

    def test_authenticated_schedule_is_saved_and_reloaded(self):
        payload = {"clock": 1790000000, "schedule": dict(DEFAULT_SCHEDULE, enabled=True)}
        client = invoke("POST", "/api/power/schedule", payload, key="test-only-secret")
        main.service(client, self.engine, self.power)
        self.assertIn(b"200 OK", client.written)
        self.assertEqual(response_body(client)["schedule"], payload["schedule"])
        self.assertEqual(PowerRuntime().work.config, payload["schedule"])
        self.assertIsNone(self.power.plan_sleep())

    def test_time_endpoint_requires_admin_and_updates_anchor(self):
        bad = invoke("POST", "/api/time", {"clock": 1790000000})
        main.service(bad, self.engine, self.power)
        self.assertIn(b"403 Forbidden", bad.written)
        ok = invoke("POST", "/api/time", {"clock": 1790000000}, "test-only-secret")
        main.service(ok, self.engine, self.power)
        self.assertIn(b"200 OK", ok.written)
        self.assertEqual(self.power.now(), 1790000000)
        self.power.tick(2500)
        self.assertEqual(self.power.now(), 1790000002)

    def test_shake_configuration_requires_auth_and_persists(self):
        motion = MotionEffects()
        payload = {"shake_enabled": True}
        bad = invoke("POST", "/api/motion/settings", payload)
        main.service(bad, self.engine, self.power, motion)
        self.assertIn(b"403 Forbidden", bad.written)
        self.assertFalse(motion.shake_enabled)
        good = invoke("POST", "/api/motion/settings", payload, "test-only-secret")
        main.service(good, self.engine, self.power, motion)
        self.assertIn(b"200 OK", good.written)
        self.assertTrue(motion.shake_enabled)
        loaded = MotionEffects()
        main.load_motion_settings(loaded)
        self.assertTrue(loaded.shake_enabled)
        get = invoke("GET", "/api/motion")
        main.service(get, self.engine, self.power, motion)
        self.assertTrue(response_body(get)["shake_enabled"])


if __name__ == "__main__":
    unittest.main()
