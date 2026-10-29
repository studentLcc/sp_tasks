from datetime import date, datetime
from zoneinfo import ZoneInfo
import unittest

from bridge.classify import classify_tasks, render_message

TZ = ZoneInfo("Asia/Shanghai")
TODAY = date(2026, 10, 29)


class ClassifyTests(unittest.TestCase):
    def test_groups_overdue_today_and_week(self):
        raw = [
            {"id": "1", "title": "补报告", "dueDay": "2026-10-27"},
            {"id": "2", "title": "写周报", "dueDay": "2026-10-29", "notes": "<p>上午发给主管</p>"},
            {
                "id": "3",
                "title": "看牙",
                "dueWithTime": int(datetime(2026, 11, 2, 9, 0, tzinfo=TZ).timestamp() * 1000),
            },
            {"id": "4", "title": "下月", "dueDay": "2026-11-20"},
            {"id": "5", "title": "收件箱"},
            {"id": "6", "title": "已完成", "dueDay": "2026-10-29", "isDone": True},
        ]
        groups = classify_tasks(raw, TODAY, TZ)
        self.assertEqual([item["title"] for item in groups["overdue"]], ["补报告"])
        self.assertEqual([item["title"] for item in groups["today"]], ["写周报"])
        self.assertEqual([item["title"] for item in groups["week"]], ["看牙"])
        self.assertEqual(groups["today"][0]["notes"], "上午发给主管")
        self.assertEqual(groups["week"][0]["schedule_time"], "09:00")
        message = render_message(groups, TODAY)
        self.assertIn("已过期（1）", message)
        self.assertIn("时间：2026-10-27", message)
        self.assertIn("时间：2026-11-02 09:00", message)
        self.assertIn("内容：上午发给主管", message)
        self.assertIn("今天（1）", message)
        self.assertIn("一周内（1）", message)
        self.assertNotIn("下月", message)
        self.assertNotIn("收件箱", message)


if __name__ == "__main__":
    unittest.main()
