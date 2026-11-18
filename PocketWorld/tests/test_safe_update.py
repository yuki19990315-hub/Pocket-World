import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firmware"))
from safe_update import MAX_FILE_SIZE, receive_update, valid_filename


class FakeConnection:
    def __init__(self, data):
        self.data = data
    def recv(self, length):
        block, self.data = self.data[:length], self.data[length:]
        return block


class TestSafeUpdate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def test_allowed_names(self):
        self.assertTrue(valid_filename("index.html"))
        self.assertTrue(valid_filename("world_model.py"))
        self.assertTrue(valid_filename("assets/tree.png"))
        for name in ("main.py", "settings.py", "worlds.json", "../main.py",
                     "assets/../main.py", "assets/x.py", "assets/.hidden.json", "/index.html"):
            self.assertFalse(valid_filename(name), name)

    def test_save_and_keep_backup(self):
        with open("index.html", "wb") as old:
            old.write(b"old")
        self.assertEqual(receive_update("index.html", 7, b"new", FakeConnection(b"site")), 7)
        with open("index.html", "rb") as newer:
            self.assertEqual(newer.read(), b"newsite")
        with open("index.html.bak", "rb") as backup:
            self.assertEqual(backup.read(), b"old")

    def test_rejected_size_does_not_change_file(self):
        with open("index.html", "wb") as old:
            old.write(b"old")
        with self.assertRaises(ValueError):
            receive_update("index.html", MAX_FILE_SIZE + 1, b"", FakeConnection(b""))
        with open("index.html", "rb") as current:
            self.assertEqual(current.read(), b"old")

    def test_interrupted_stream_keeps_old_data(self):
        with open("index.html", "wb") as old:
            old.write(b"original")
        with self.assertRaises(ValueError):
            receive_update("index.html", 20, b"hello", FakeConnection(b"world"))
        with open("index.html", "rb") as current:
            self.assertEqual(current.read(), b"original")
        self.assertFalse(os.path.exists("index.html.incoming"))

    def test_invalid_python_is_not_activated(self):
        with open("world_model.py", "w") as old:
            old.write("valid = True\n")
        bad = b"def broken(:\n"
        with self.assertRaises(SyntaxError):
            receive_update("world_model.py", len(bad), bad, FakeConnection(b""))
        with open("world_model.py") as current:
            self.assertEqual(current.read(), "valid = True\n")


if __name__ == "__main__":
    unittest.main()
