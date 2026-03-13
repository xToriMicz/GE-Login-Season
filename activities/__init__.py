# -*- coding: utf-8 -*-
"""
Registry กิจกรรม — auto-scan ge_*.py files + manual fallback.
เพิ่มกิจกรรมใหม่: สร้างไฟล์ activities/ge_xxx.py ที่มี activity = Activity(...)
ระบบจะ scan หาอัตโนมัติ ไม่ต้องแก้ไฟล์นี้
"""

import importlib
import pkgutil
from .base import Activity

# Auto-discover: scan ge_*.py modules for .activity attribute
_ALL: list[Activity] = []
for _finder, _name, _ispkg in pkgutil.iter_modules(__path__):
    if not _name.startswith("ge_"):
        continue
    try:
        _mod = importlib.import_module(f".{_name}", __package__)
        if hasattr(_mod, "activity") and isinstance(_mod.activity, Activity):
            _ALL.append(_mod.activity)
    except Exception:
        pass

# Fallback: ถ้า auto-scan ไม่เจอเลย ใช้ manual import
if not _ALL:
    from . import ge_daily_login
    _ALL = [
        ge_daily_login.activity,
    ]


def get_activity(activity_id: str) -> Activity | None:
    """คืนกิจกรรมที่ id ตรง ไม่เจอคืน None"""
    for a in _ALL:
        if a.id == activity_id:
            return a
    return None


def list_activities() -> list[Activity]:
    """คืนรายการกิจกรรมทั้งหมด"""
    return list(_ALL)
