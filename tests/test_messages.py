import importlib.util
import os
import unittest

_UTIL = os.path.join(os.path.dirname(__file__), "..", "custom_components", "sp_tasks", "util.py")
_SPEC = importlib.util.spec_from_file_location("sp_tasks_util", _UTIL)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
format_markdown = _MODULE.format_markdown
serverchan_url = _MODULE.serverchan_url


class MessageTests(unittest.TestCase):
    def test_serverchan3_url_extracts_uid(self):
        self.assertEqual(
            serverchan_url("sctp123tSECRET"),
            "https://123.push.ft07.com/send/sctp123tSECRET.send",
        )

    def test_serverchan3_url_requires_uid_when_missing(self):
        with self.assertRaises(ValueError):
            serverchan_url("sctpSECRET")

    def test_markdown_renders_tasks(self):
        text = format_markdown({"tasks": [{"title": "写周报", "is_done": False, "notes": "上午"}]}, "2026-10-29")
        self.assertIn("- [ ] 写周报", text)
        self.assertIn("上午", text)


if __name__ == "__main__":
    unittest.main()
