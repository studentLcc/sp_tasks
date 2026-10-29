import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bridge.app import Bridge, Settings, normalize_task  # noqa: E402


class BridgeTests(unittest.TestCase):
    def test_normalize_task(self):
        task = normalize_task({"id": "1", "title": "  写周报 ", "isDone": 0, "tagIds": None}, "2026-10-29")
        self.assertEqual(task["title"], "写周报")
        self.assertFalse(task["is_done"])
        self.assertEqual(task["tag_ids"], [])

    @patch("bridge.app._json_request")
    def test_sync_reads_today_and_posts_to_ha(self, request):
        request.side_effect = [
            {"ok": True, "data": [{"id": "1", "title": "写周报", "dueDay": "2026-10-29"}]},
            {"ok": True, "accepted": 1},
        ]
        settings = Settings(
            sp_api_url="http://sp",
            sp_api_token="sp-token",
            ha_url="http://ha:8123",
            ha_token="ha-token",
        )
        with patch("bridge.app.date") as mocked_date:
            mocked_date.today.return_value.isoformat.return_value = "2026-10-29"
            result = Bridge(settings).sync()
        self.assertEqual(result["task_count"], 1)
        self.assertEqual(request.call_args_list[0].kwargs["token"], "sp-token")
        self.assertEqual(request.call_args_list[1].kwargs["token"], "ha-token")
        payload = request.call_args_list[1].kwargs["payload"]
        self.assertEqual(payload["tasks"][0]["title"], "写周报")


if __name__ == "__main__":
    unittest.main()

