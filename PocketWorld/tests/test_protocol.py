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


if __name__ == "__main__":
    unittest.main()
