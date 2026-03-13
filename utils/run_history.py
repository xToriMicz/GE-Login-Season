# -*- coding: utf-8 -*-
"""
Run History — เก็บประวัติผลลัพธ์ทุก run เป็น JSON
ใช้สำหรับ Report แสดง trend, ID ที่ fail บ่อย, เปรียบเทียบ run
"""

import json
from datetime import datetime
from pathlib import Path

HISTORY_DIR = Path("reports")


def save_run_history(results: list, start_time: datetime, end_time: datetime,
                     activity_id: str, account_file: str = "") -> Path:
    """
    บันทึกผลลัพธ์ run เป็น JSON ไฟล์
    returns: path ของไฟล์ที่บันทึก
    """
    history_dir = HISTORY_DIR / activity_id / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    timestamp = start_time.strftime("%Y%m%d_%H%M%S")

    success_count = len([r for r in results if r["status"]])
    fail_count = len([r for r in results if not r["status"]])

    data = {
        "activity_id": activity_id,
        "account_file": account_file,
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": int((end_time - start_time).total_seconds()),
        "total": len(results),
        "success": success_count,
        "fail": fail_count,
        "success_rate": round(success_count / len(results) * 100, 1) if results else 0,
        "results": [
            {
                "id": r["id"],
                "status": r["status"],
                "message": r["message"],
                "time": r["time"],
                "screenshot": r.get("screenshot"),
                "extra": r.get("extra", {}),
            }
            for r in results
        ],
    }

    file_path = history_dir / f"run_{timestamp}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return file_path


def load_recent_runs(activity_id: str, limit: int = 7) -> list[dict]:
    """โหลด N runs ล่าสุดของ activity (เรียงจากใหม่สุด)"""
    history_dir = HISTORY_DIR / activity_id / "history"
    if not history_dir.exists():
        return []

    files = sorted(history_dir.glob("run_*.json"), reverse=True)[:limit]
    runs = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                runs.append(json.load(fp))
        except (json.JSONDecodeError, OSError):
            continue
    return runs


def get_frequent_failures(activity_id: str, runs: int = 7, min_fails: int = 2) -> list[dict]:
    """หา ID ที่ fail บ่อยใน N runs ล่าสุด"""
    recent = load_recent_runs(activity_id, limit=runs)
    if not recent:
        return []

    fail_counts: dict[str, int] = {}
    total_runs = len(recent)

    for run in recent:
        for r in run.get("results", []):
            if not r["status"]:
                fail_counts[r["id"]] = fail_counts.get(r["id"], 0) + 1

    frequent = [
        {"id": uid, "fail_count": count, "total_runs": total_runs}
        for uid, count in fail_counts.items()
        if count >= min_fails
    ]
    frequent.sort(key=lambda x: x["fail_count"], reverse=True)
    return frequent
