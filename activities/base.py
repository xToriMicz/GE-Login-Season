# -*- coding: utf-8 -*-
"""
Base สำหรับกิจกรรม (activity) แต่ละเกม/แต่ละงาน.
แต่ละกิจกรรมเป็น 1 module แยกไฟล์ ลงทะเบียนใน activities/__init__.py
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

# Type สำหรับ page (Playwright) ไม่ต้อง import ที่นี่
Page = object


@dataclass
class Activity:
    """ข้อมูลกิจกรรมเดียว — ใช้โดย login flow หลัง login แล้ว"""

    id: str
    """รหัสใช้กับ --activity เช่น ge-leonardo-new-year-2026"""
    name: str
    """ชื่อแสดง เช่น GE Leonardo New Year 2026"""
    url: str
    """URL หน้ากิจกรรม (ต้อง login ก่อนถึงเข้าได้)"""
    wait_seconds: int
    """รอบนหน้ากิจกรรมกี่วินาทีก่อน logout"""
    run_after_goto: Optional[Callable[["Activity", "Page", int, int, str, Optional[Path]], None]] = None
    """
    ฟังก์ชันเพิ่มเติมหลัง goto แล้ว (ถ้ามี).
    รับ (activity, page, n, total, exe_id, screenshot_dir) — ใช้ทำขั้นตอนเฉพาะกิจกรรม เช่น คลิกรับรางวัล
    """
    extra_data: Optional[dict] = None
    """ข้อมูลเพิ่มเติมสำหรับกิจกรรมเฉพาะทาง เช่น item_code"""
    report_columns: List[dict] = field(default_factory=list)
    """
    คอลัมน์พิเศษใน Report เฉพาะกิจกรรมนี้ — แต่ละ dict มี:
      key: ชื่อ key ใน extra_data (เช่น "claim_count")
      label: หัวคอลัมน์ (เช่น "Days Claimed")
      icon: emoji นำหน้า (เช่น "📅") — optional
    """
