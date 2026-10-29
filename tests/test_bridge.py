import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from bridge.app import Bridge, Settings  # noqa: E402


class BridgeTests(unittest.TestCase):
    @patch("bridge.app._json_request")
    def test_sync_posts_classified_message(self, request):
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
        request.side_effect = [
            {
                "ok": True,
                "data": [
                    {"id": "1", "title": "补报告", "dueDay": (today - timedelta(days=1)).isoformat()},
                    {"id": "2", "title": "写周报", "dueDay": today.isoformat()},
                    {"id": "3", "title": "看牙", "dueDay": (today + timedelta(days=2)).isoformat()},
                ],
            },
            {"ok": True},
        ]
        result = Bridge(
            Settings(
                sp_api_url="http://sp",
                sp_api_token="sp-token",
                ha_url="http://ha:8123",
                ha_token="ha-token",
                timezone="Asia/Shanghai",
            )
        ).sync()
        self.assertEqual(result["task_count"], 3)
        payload = request.call_args_list[1].kwargs["payload"]
        self.assertIn("已过期（1）", payload["message"])
        self.assertIn("今天（1）", payload["message"])
        self.assertIn("一周内（1）", payload["message"])
        self.assertNotIn("tagId=TODAY", request.call_args_list[0].args[0])


if __name__ == "__main__":
    unittest.main()
