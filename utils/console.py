# -*- coding: utf-8 -*-
"""
การแสดงสถานะลง terminal (CLI output).
Single Responsibility: แสดงผลข้อความสถานะเท่านั้น
flush=True ให้เห็นทันทีเมื่อรัน headless/จาก UI
มีเวลา (HH:MM:SS) ในแต่ละบรรทัด — ดูว่าแต่ละขั้นตอนใช้เวลาเท่าไร
Thread-safe: ใช้ Lock ป้องกัน output ซ้อนกันเมื่อรัน --parallel
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path

_print_lock = threading.Lock()

# Progress file — อยู่ใน project root
_PROGRESS_FILE = Path(__file__).resolve().parent.parent / ".progress.json"


def status(n: int, total: int, message: str, exe_id: str = "") -> None:
    """พิมพ์สถานะรูปแบบ [HH:MM:SS] [n/N] (exe_id) message ลง stdout — flush ให้เห็นทันที (thread-safe)"""
    t = datetime.now().strftime("%H:%M:%S")
    prefix = f"[{t}] [{n}/{total}]"
    line = f"{prefix} ({exe_id}) {message}" if exe_id else f"{prefix} {message}"
    with _print_lock:
        print(line, flush=True)


def save_progress(result_entry: dict, total: int, activity: str, file: str, status_str: str = "running") -> None:
    """บันทึก progress ลง .progress.json — append result แล้ว atomic write (thread-safe)

    result_entry: {"index": int, "id": str, "status": bool, "time": str}
    completed = len(results) — source of truth สำหรับ progress bar
    """
    tmp_path = _PROGRESS_FILE.with_suffix(".tmp")
    with _print_lock:
        try:
            # อ่านข้อมูลเดิม (ถ้ามี)
            existing = {}
            if _PROGRESS_FILE.exists():
                try:
                    with open(_PROGRESS_FILE, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except (OSError, json.JSONDecodeError):
                    pass

            results = existing.get("results", [])
            results.append(result_entry)

            data = {
                "activity": activity,
                "file": file,
                "total": total,
                "status": status_str,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "completed": len(results),
                "results": results,
            }
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(str(tmp_path), str(_PROGRESS_FILE))
        except OSError:
            pass


def init_progress(total: int, activity: str, file: str) -> None:
    """เริ่มต้น .progress.json ใหม่ — เรียกตอนเริ่มรัน (ก่อน loop)"""
    data = {
        "activity": activity,
        "file": file,
        "total": total,
        "status": "running",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "completed": 0,
        "results": [],
    }
    tmp_path = _PROGRESS_FILE.with_suffix(".tmp")
    with _print_lock:
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(str(tmp_path), str(_PROGRESS_FILE))
        except OSError:
            pass


def clear_progress() -> None:
    """เคลียร์ progress — set status=completed (ไม่ลบไฟล์ ตาม Nothing is Deleted)"""
    if not _PROGRESS_FILE.exists():
        return
    try:
        with open(_PROGRESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["status"] = "completed"
        data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tmp_path = _PROGRESS_FILE.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(str(tmp_path), str(_PROGRESS_FILE))
    except (OSError, json.JSONDecodeError):
        pass


def load_progress() -> dict | None:
    """อ่าน .progress.json — คืน dict หรือ None ถ้าไม่มี/อ่านไม่ได้"""
    if not _PROGRESS_FILE.exists():
        return None
    try:
        with open(_PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
