from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

CATEGORIES = ("overdue", "today", "week")
CATEGORY_TITLES = {"overdue": "已过期", "today": "今天", "week": "一周内"}


def schedule_day(task: dict[str, Any], tz: ZoneInfo) -> date | None:
    """Use the scheduled day only. Deadline is not a plan date."""
    due_with_time = task.get("dueWithTime")
    if isinstance(due_with_time, (int, float)) and due_with_time > 0:
        return datetime.fromtimestamp(due_with_time / 1000, tz).date()
    due_day = task.get("dueDay")
    if isinstance(due_day, str):
        try:
            return date.fromisoformat(due_day[:10])
        except ValueError:
            pass
    planned_at = task.get("plannedAt")
    if isinstance(planned_at, (int, float)) and planned_at > 0:
        return datetime.fromtimestamp(planned_at / 1000, tz).date()
    return None


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
        day = schedule_day(task, tz)
        if day is None:
            continue
        category = _category(day, today)
        if category is None:
            continue
        groups[category].append(
            {
                "id": str(task.get("id") or ""),
                "title": str(task.get("title") or "").strip() or "（无标题）",
                "notes": task.get("notes") or "",
                "schedule_day": day.isoformat(),
                "category": category,
                "parent_id": task.get("parentId"),
            }
        )
    for items in groups.values():
        items.sort(key=lambda item: (item["schedule_day"], item["title"]))
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
            lines.append(f"- {item['schedule_day']} {item['title']}")
            lines.append("")
    return "\n".join(lines).strip()
