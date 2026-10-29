from __future__ import annotations

import re
from typing import Any


def clean_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def format_markdown(task_data: dict[str, Any], task_date: str) -> str:
    tasks = task_data.get("tasks", [])
    lines = [f"## Super Productivity 任务（{task_date}）", ""]
    if not tasks:
        lines.append("今天没有待办任务。")
        return "\n".join(lines)
    for task in tasks:
        mark = "x" if task.get("is_done") else " "
        title = task.get("title") or "（无标题）"
        lines.append(f"- [{mark}] {title}")
        notes = clean_text(task.get("notes"))
        if notes:
            lines.append(f"  - {notes}")
    return "\n".join(lines)


def serverchan_url(sendkey: str, uid: str = "") -> str:
    if sendkey.startswith("sctp"):
        match = re.match(r"sctp(\d+)t", sendkey)
        resolved_uid = uid or (match.group(1) if match else "")
        if not resolved_uid:
            raise ValueError("Server酱³ SendKey 需要 uid，或使用 sctp<uid>t... 格式")
        return f"https://{resolved_uid}.push.ft07.com/send/{sendkey}.send"
    if not sendkey:
        raise ValueError("缺少 Server酱 SendKey")
    return f"https://sctapi.ftqq.com/{sendkey}.send"
