import os
import json
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
import main
import settings
from world_model import PocketWorld


class FakeClient:
    def __init__(self, request, chunksize=256):
        self.request = request
        self.chunksize = chunksize
        self.written = bytearray()
    def settimeout(self, seconds):
        pass
    def recv(self, maximum):
        n = min(maximum, self.chunksize)
        data, self.request = self.request[:n], self.request[n:]
        return data
    def sendall(self, data):
        self.written.extend(data)


def request(method, path, headers=None, body=b""):
    headers = headers or {}
    headerlines = "".join("%s: %s\r\n" % (key, value) for key, value in headers.items())
    return ("%s %s HTTP/1.1\r\n%s\r\n" % (method, path, headerlines)).encode() + body


class TestProtocol(unittest.TestCase):
    def setUp(self):
        self.engine = PocketWorld()
        self.original = settings.ADMIN_KEY

    def tearDown(self):
        settings.ADMIN_KEY = self.original

    def test_info(self):
        client = FakeClient(request("GET", "/api/info"))
        self.assertFalse(main.service(client, self.engine))
        self.assertIn(b"200 OK", client.written)
        self.assertEqual(json.loads(bytes(client.written).split(b"\r\n\r\n", 1)[1])["name"], "サンニー")

    def test_upload_requires_admin_key(self):
        settings.ADMIN_KEY = "secret"
        client = FakeClient(request("POST", "/api/upload", {"X-Admin-Key":"wrong", "Content-Length":"3", "X-File-Name":"index.html"}, b"abc"))
        self.assertFalse(main.service(client, self.engine))
        self.assertIn(b"403 Forbidden", client.written)

    def test_streamed_http_update(self):
        settings.ADMIN_KEY = "secret"
        data = b"<html>Sanny!</html>"
        with tempfile.TemporaryDirectory() as directory:
            old = os.getcwd()
            os.chdir(directory)
            try:
                client = FakeClient(request("POST", "/api/upload",
                    {"X-Admin-Key":"secret", "Content-Length":str(len(data)),
                     "X-File-Name":"index.html"}, data), chunksize=7)
                self.assertFalse(main.service(client, self.engine))
                self.assertIn(b"200 OK", client.written)
                with open("index.html", "rb") as saved:
                    self.assertEqual(saved.read(), data)
            finally:
                os.chdir(old)

    def test_restart_needs_auth(self):
        settings.ADMIN_KEY = "secret"
        bad = FakeClient(request("POST", "/api/restart"))
        self.assertFalse(main.service(bad, self.engine))
        good = FakeClient(request("POST", "/api/restart", {"X-Admin-Key":"secret"}))
        self.assertEqual(main.service(good, self.engine), "restart")

    def test_device_mode_changes_persist_without_changing_phone_world(self):
        class Screen:
            selected = "nature"
            water_area = "river"
            def choose(self, world):
                if world not in ("nature", "city"):
                    raise ValueError("Unknown world")
                self.selected = world
            def choose_water_area(self, area):
                self.water_area = area
            def show(self, minutes, force=False):
                return True
            def status(self):
                return {"selected": self.selected, "connected": True}
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                body = b'{"world":"city"}'
                screen = Screen()
                client = FakeClient(request("POST", "/api/display/select",
                    {"Content-Length":str(len(body))}, body), chunksize=5)
                self.assertFalse(main.service(client, self.engine, screen=screen))
                self.assertIn(b"200 OK", client.written)
                self.assertEqual(screen.selected, "city")
                with open("display.json") as saved:
                    self.assertEqual(json.load(saved)["world"], "city")
                main.load_display_selection(Screen())
            finally:
                os.chdir(previous)

    def test_invalid_mode_is_not_persisted(self):
        class Screen:
            selected = "nature"
            def choose(self, world):
                raise ValueError("Unknown world")
        client = FakeClient(request("POST", "/api/display/select",
            {"Content-Length":"17"}, b'{"world":"alien"}'))
        self.assertFalse(main.service(client, self.engine, screen=Screen()))
        self.assertIn(b"400 Bad Request", client.written)

    def test_aquarium_area_requires_unlock(self):
        class Screen:
            selected = "nature"
            water_area = "river"
            def choose(self, ident):
                self.selected = ident
            def choose_water_area(self, area):
                self.water_area = area
            def show(self, minutes, force=False):
                return True
            def status(self):
                return {"selected": self.selected, "water_area": self.water_area}
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                screen = Screen()
                body = b'{"world":"aquarium","area":"deepsea"}'
                client = FakeClient(request("POST", "/api/display/select",
                    {"Content-Length":str(len(body))}, body))
                main.service(client, self.engine, screen=screen)
                self.assertIn(b"400 Bad Request", client.written)
                self.assertEqual(screen.selected, "nature")
                self.engine.worlds["aquarium"]["water_areas"]["deepsea"]["unlocked"] = True
                client = FakeClient(request("POST", "/api/display/select",
                    {"Content-Length":str(len(body))}, body))
                main.service(client, self.engine, screen=screen)
                self.assertIn(b"200 OK", client.written)
                self.assertEqual(screen.water_area, "deepsea")
                with open("display.json") as saved:
                    self.assertEqual(json.load(saved)["water_area"], "deepsea")
            finally:
                os.chdir(previous)

    def test_art_file_is_streamed(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                os.mkdir("assets")
                with open("assets/river-mature.png", "wb") as f:
                    f.write(b"PNG fixture")
                client = FakeClient(request("GET", "/assets/river-mature.png"))
                self.assertFalse(main.service(client, self.engine))
                self.assertIn(b"Content-Type: image/png", client.written)
                self.assertTrue(client.written.endswith(b"PNG fixture"))
                invalid = FakeClient(request("GET", "/assets/../worlds.json"))
                self.assertFalse(main.service(invalid, self.engine))
                self.assertIn(b"404 Not Found", invalid.written)
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
