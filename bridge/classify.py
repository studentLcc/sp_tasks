from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any
from zoneinfo import ZoneInfo

CATEGORIES = ("overdue", "today", "week")
CATEGORY_TITLES = {"overdue": "已过期", "today": "今天", "week": "一周内"}


def _moment(value: Any, tz: ZoneInfo) -> datetime | None:
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(value / 1000, tz)
    return None


def schedule_point(task: dict[str, Any], tz: ZoneInfo) -> tuple[date | None, str]:
    """Return the scheduled date and clock time. A date-only plan has no clock time."""
    due_with_time = _moment(task.get("dueWithTime"), tz)
    if due_with_time is not None:
        return due_with_time.date(), due_with_time.strftime("%H:%M")
    due_day = task.get("dueDay")
    if isinstance(due_day, str):
        try:
            return date.fromisoformat(due_day[:10]), ""
        except ValueError:
            pass
    planned_at = _moment(task.get("plannedAt"), tz)
    if planned_at is not None:
        return planned_at.date(), planned_at.strftime("%H:%M")
    return None, ""


def task_content(value: Any) -> str:
    if value is None:
        return "无"
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or "无"


def _category(day: date, today: date) -> str | None:
    delta = (day - today).days
    if delta < 0:
        return "overdue"
    if delta == 0:
        return "today"
    if delta <= 7:
        return "week"
    return None


def classify_tasks(raw_tasks: list[dict[str, Any]], today: date, tz: ZoneInfo) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {key: [] for key in CATEGORIES}
    for task in raw_tasks:
        if not isinstance(task, dict) or task.get("isDone"):
            continue
        day, clock = schedule_point(task, tz)
        if day is None:
            continue
        category = _category(day, today)
        if category is None:
            continue
        groups[category].append(
            {
                "id": str(task.get("id") or ""),
                "title": str(task.get("title") or "").strip() or "（无标题）",
                "notes": task_content(task.get("notes")),
                "schedule_day": day.isoformat(),
                "schedule_time": clock,
                "category": category,
                "parent_id": task.get("parentId"),
            }
        )
    for items in groups.values():
        items.sort(key=lambda item: (item["schedule_day"], item["schedule_time"], item["title"]))
    return groups


def render_message(groups: dict[str, list[dict[str, Any]]], today: date) -> str:
    lines = [f"任务（{today.isoformat()}）", ""]
    for key in CATEGORIES:
        items = groups.get(key) or []
        lines.append(f"{CATEGORY_TITLES[key]}（{len(items)}）")
        lines.append("")
        if not items:
            lines.append("无")
            lines.append("")
            continue
        for item in items:
            when = item["schedule_day"]
            if item.get("schedule_time"):
                when = f"{when} {item['schedule_time']}"
            lines.append(f"- {item['title']}")
            lines.append(f"  时间：{when}")
            lines.append(f"  内容：{item.get('notes') or '无'}")
            lines.append("")
    return "\n".join(lines).strip()
