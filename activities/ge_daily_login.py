# -*- coding: utf-8 -*-
"""
กิจกรรม GE Season Server Daily Login.
กดรับของทุกวัน — คลิกเฉพาะ slot ที่มีแถบเขียว "Day x" (รับวันนี้ได้) เท่านั้น.
สำหรับ Season Server ที่เปิดใหม่.
"""

from pathlib import Path
from typing import Optional
from .base import Activity
from .daily_login_detection import is_slot_claimable
from utils.navigation import wait_for_content
from core.delays import (
    DAILY_LOGIN_AFTER_CLICK_SLOT_MS,
    DAILY_LOGIN_AFTER_CLOSE_MS,
    DAILY_LOGIN_AFTER_SCROLL_MS,
    DAILY_LOGIN_INITIAL_MS,
    DAILY_LOGIN_POPUP_CLOSE_WAIT_MS,
)
from utils.console import status
from utils.screenshots import save_screenshot


def _is_error_page(page) -> bool:
    """ตรวจว่าหน้าปัจจุบันเป็น Chrome error page หรือไม่"""
    try:
        title = page.title().lower()
        if any(x in title for x in ["can't be reached", "not be reached", "err_", "is not available"]):
            return True
        content = page.locator("body").inner_text(timeout=2000)
        if any(x in content for x in ["ERR_CONNECTION_TIMED_OUT", "ERR_CONNECTION_REFUSED",
                                        "This site can\u2019t be reached", "took too long to respond",
                                        "502 Bad Gateway", "504 Gateway"]):
            return True
    except Exception:
        pass
    return False


def _run_daily_login_claim(activity: Activity, page, n: int, total: int, exe_id: str, screenshot_dir: Optional[Path] = None) -> None:
    """หลังเข้าหน้ากิจกรรม: คลิกรับของ (Day ที่มีแถบเขียว) แล้วกด CLOSE — ไม่ซ้ำ: จำวันที่รับแล้ว หาเฉพาะ Day ใหญ่กว่านั้น"""
    max_days = 21
    max_claims = 21  # ป้องกัน loop ไม่จบ
    claim_count = 0
    last_claimed_day = 0  # รอบถัดไปหาเฉพาะ Day > ค่านี้ — ลดการกดซ้ำ
    status(n, total, "รอหน้ากิจกรรมโหลด...", exe_id)
    page.wait_for_timeout(DAILY_LOGIN_INITIAL_MS)

    # ใช้ utility จัดการรอคอนเทนต์ (ถ้าไม่มาจะ F5 เอง)
    if not wait_for_content(page, "#reward-day-1", n, total, exe_id):
        return

    while claim_count < max_claims:
        claimable_slot = None
        claimable_day_num = 0
        
        # หา slot แรกที่ "รับวันนี้ได้" — เริ่มจาก Day (last_claimed_day+1) เป็นต้นไป ไม่วนกลับไป Day 1
        for day in range(last_claimed_day + 1, max_days + 1):
            # ลองหาจาก ID ก่อน (แม่นยำกว่า เช่น #reward-day-1)
            slot = page.locator(f"#reward-day-{day}").first
            
            # ถ้าไม่เจอ ID ลองหาจาก text (เผื่อโครงสร้างเว็บเปลี่ยน)
            if slot.count() == 0:
                day_text = f"Day {day}"
                slot = page.get_by_text(day_text, exact=False).first
                
            if slot.count() == 0:
                continue
                
            if not is_slot_claimable(slot):
                continue
                
            claimable_slot = slot
            claimable_day_num = day
            break

        if claimable_slot is None:
            break  # ไม่มีปุ่มเขียว Day ถัดไปแล้ว — ออก

        try:
            claimable_slot.scroll_into_view_if_needed()
            page.wait_for_timeout(DAILY_LOGIN_AFTER_SCROLL_MS)
            
            # คลิกที่ slot (ตัว button หรือ div ที่ครอบคลุม)
            claimable_slot.click()
            page.wait_for_timeout(DAILY_LOGIN_AFTER_CLICK_SLOT_MS)
            
            # รอและกด CLOSE ใน popup
            close_btn = page.get_by_role("button", name="CLOSE").or_(page.get_by_text("CLOSE", exact=True)).first
            close_btn.wait_for(state="visible", timeout=DAILY_LOGIN_POPUP_CLOSE_WAIT_MS)
            close_btn.click()
            
            claim_count += 1
            last_claimed_day = claimable_day_num  # จำวันที่รับแล้ว — รอบถัดไปไม่ดู Day นี้ซ้ำ
            status(n, total, f"รับของ Day {claimable_day_num} แล้ว", exe_id)
            page.wait_for_timeout(DAILY_LOGIN_AFTER_CLOSE_MS)
        except Exception:
            break

    # 3. ตรวจจับหน้า error (server ล่มระหว่าง claim)
    if _is_error_page(page):
        error_ss = None
        if screenshot_dir:
            error_ss = save_screenshot(page=page, exe_id=exe_id, activity_id=activity.id,
                                       screenshot_dir=screenshot_dir, suffix="error", full_page=False)
        status(n, total, "Server ล่มระหว่างรับของ", exe_id)
        raise Exception(f"Server ล่มระหว่างรับของ (กดรับได้ {claim_count} วัน ก่อน server ล่ม)")

    # 4. Reload หน้าเพื่อให้ DOM อัปเดตสถานะ "รับไอเทมแล้ว" ก่อนถ่ายรูปหลักฐาน
    if claim_count > 0:
        try:
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(2_000)
        except Exception:
            pass

    # 5. ถ่ายภาพหน้าจอ (Proof Screenshot)
    final_ss = None
    if screenshot_dir:
        # เช็คอีกทีหลัง reload — ถ้า error ก็ถ่ายเป็น "error" ไม่ใช่ "claim"
        suffix = "error" if _is_error_page(page) else "claim"
        final_ss = save_screenshot(
            page=page, exe_id=exe_id, activity_id=activity.id,
            screenshot_dir=screenshot_dir, suffix=suffix, full_page=True
        )
        if final_ss:
            status(n, total, f"📸 บันทึกหลักฐานกิจกรรม: {Path(final_ss).name}", exe_id)

    status(n, total, f"รับของครบแล้ว (กดรับ {claim_count} วัน)", exe_id)
    return {"screenshot": final_ss, "claim_count": claim_count, "last_day": last_claimed_day}


def _daily_login_url() -> str:
    """สร้าง URL อัตโนมัติตามเดือน/ปีปัจจุบัน (เช่น mar-2026, apr-2026)"""
    from datetime import datetime
    now = datetime.now()
    month_abbr = now.strftime("%b").lower()  # jan, feb, mar, ...
    return f"https://activities2.exe.in.th/dl/granado-espada-new-season-server/ge-new-season-server-daily-login-{month_abbr}-{now.year}/main"

activity = Activity(
    id="ge-season-daily-login",
    name="GE Season Server Daily Login (ทุกวัน)",
    url=_daily_login_url(),
    wait_seconds=3,
    run_after_goto=_run_daily_login_claim,
    report_columns=[
        {"key": "claim_count", "label": "Claimed", "icon": "📅"},
        {"key": "last_day", "label": "Last Day", "icon": "🎯"},
    ],
)
