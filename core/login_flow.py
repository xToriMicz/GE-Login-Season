# -*- coding: utf-8 -*-
"""
Logic การ login -> ไปหน้ากิจกรรม -> รอ -> logout (ต่อหนึ่งบัญชี).
Single Responsibility: โฟลว์การทำงานบนเบราว์เซอร์เท่านั้น ไม่รวม CLI/argparse
"""

import random
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.delays import (
    ACTIVITY_GOTO_SETTLE_MS,
    AFTER_LOGIN_CLICK_MS,
    AFTER_SECOND_LOGIN_MS,
    LOGIN_FORM_WAIT_TIMEOUT_MS,
    LOGIN_INPUT_WAIT_TIMEOUT_MS,
    LOGOUT_CLICK_TIMEOUT_MS,
    LOGOUT_FALLBACK_TIMEOUT_MS,
    NAVIGATION_TIMEOUT_MS,
    PAGE_SETTLE_AFTER_GOTO_MS,
    PAGE_SETTLE_AFTER_LOGIN_MS,
)
from utils.agent import human_delay, bypass_cloudflare
from utils.console import status
from core.login_handlers import handle_login_any, check_login_error_any
from utils.preview import save_preview





from utils.screenshots import save_screenshot
from utils.navigation import safe_goto


def run_login_flow(
    page,
    exe_id: str,
    password: str,
    n: int,
    total: int,
    login_url: str,
    activity,  # activities.base.Activity
    use_agent: bool = True,
    human_type: bool = False,
    screenshot_dir: Optional[Path] = None,
    preview_mode: bool = False,
) -> dict:
    """
    Dynamic Flow with Step Tracking:
    """
    current_step = "เตรียมการหลัก"
    saved_screenshot = None
    try:
        # 1. ไปหน้ากิจกรรมโดยตรง
        current_step = "เข้าหน้ากิจกรรม (Navigate)"
        status(n, total, f"วิ่งไปหน้ากิจกรรม: {activity.name} ...", exe_id)
        safe_goto(page, activity.url, n, total, exe_id)
        
        # 2. ตรวจสอบว่าต้องล็อกอินไหม
        current_url = page.url.lower()
        needs_login = (
            "passport.exe.in.th" in current_url or 
            "accounts.exe.in.th" in current_url or
            page.locator('input[name="password"], input[type="password"]').count() > 0
        )

        if needs_login:
            current_step = "ล็อกอิน (Login)"
            status(n, total, "ตรวจพบหน้า Login กำลังดำเนินการล็อกอิน ...", exe_id)
            if use_agent:
                human_delay(0.5, 1.2)
                bypass_cloudflare(page, n, total, exe_id, status)
            
            # Preview callback: capture screen after filling credentials
            def on_filled(p):
                if preview_mode:
                    save_preview(p)
            
            if not handle_login_any(page, exe_id, password, n, total, use_agent, human_type, on_filled_callback=on_filled):
                # ถ้า handler พลาด (เช่น timeout) ให้ถ่ายโพรไฟล์และหยุดเลย
                _take_screenshot(page, exe_id, activity, screenshot_dir)
                raise Exception("ขั้นตอนกรอก Login ผิดพลาด (Timeout/Element not found)")
            
            # ตรวจสอบว่า Login พลาดไหม (ตามที่ User แจ้ง: ID/Pass ผิด)
            login_err = check_login_error_any(page)
            if login_err:
                _take_screenshot(page, exe_id, activity, screenshot_dir)
                raise Exception(login_err)

            page.wait_for_timeout(PAGE_SETTLE_AFTER_LOGIN_MS)
            
            # ตรวจสอบว่าหลังจากกด Login แล้วยังติดหน้าเดิมอยู่ไหม (ถ้ายังติดแปลว่ามีปัญหา)
            if "passport.exe.in.th" in page.url or "accounts.exe.in.th" in page.url:
                 # ลองรีเฟรชหรือไปหน้ากิจกรรมตรงๆ อีก 1 ครั้ง
                 status(n, total, "ยังติดหน้าเดิมหลังจาก Login กำลังพยายามเข้าหน้ากิจกรรม...", exe_id)
                 safe_goto(page, activity.url, n, total, exe_id)
                 
                 # ถ้ายังเป็นหน้า Login อีก แสดงว่า Login ไม่ผ่านจริงๆ
                 if "passport.exe.in.th" in page.url or "accounts.exe.in.th" in page.url:
                     _take_screenshot(page, exe_id, activity, screenshot_dir)
                     raise Exception("Login ไม่สำเร็จ (ติดหน้า Login เดิม)")

        # 3. จัดการ Re-auth
        if "accounts.exe.in.th" in page.url or "passport.exe.in.th" in page.url:
            current_step = "ยืนยันตัวตนซ้ำ (Re-auth)"
            status(n, total, "เจอหน้ายืนยันตัวตนอีกชั้น (Re-auth) ...", exe_id)
            handle_login_any(page, exe_id, password, n, total, use_agent, human_type)
            page.wait_for_timeout(AFTER_SECOND_LOGIN_MS)

        page.wait_for_timeout(ACTIVITY_GOTO_SETTLE_MS)

        # 4. ทำกิจกรรมพิเศษ
        current_step = "ทำกิจกรรม (Activity Logic)"
        activity_extra_data = {}
        if activity.run_after_goto:
            # เพิ่มการถ่าย preview ก่อนเริ่มกิจกรรม
            if preview_mode: save_preview(page)
            
            # run_after_goto ควรคืนค่า path รูป หรือ dict {screenshot, ...}
            activity_result = activity.run_after_goto(activity, page, n, total, exe_id, screenshot_dir)
            if isinstance(activity_result, str):
                saved_screenshot = activity_result
            elif isinstance(activity_result, dict):
                saved_screenshot = activity_result.get("screenshot")
                # เก็บข้อมูลพิเศษอื่นๆ ไว้ส่งกลับ (เช่น participation_rights)
                for k, v in activity_result.items():
                    if k != "screenshot":
                        activity_extra_data[k] = v

        # 5. ถ่ายภาพหน้าจอ (ทั่วไป - จะถ่ายเฉพาะถ้ากิจกรรมไม่ได้ถ่ายไว้เอง)
        if screenshot_dir and not saved_screenshot:
            current_step = "ถ่ายรูปหลักฐาน (General Screenshot)"
            saved_screenshot = _take_screenshot(page, exe_id, activity, screenshot_dir)

        # 6. รอตามกำหนด และ Logout
        current_step = "รอจบกระบวนการ"
        page.wait_for_timeout(activity.wait_seconds * 1000)

        current_step = "ออกจากระบบ (Logout)"
        _do_logout(page, n, total, exe_id)
        
        return {
            "screenshot": saved_screenshot, 
            "step": "Done", 
            "error": None,
            "extra_data": activity_extra_data
        }
        
    except Exception as e:
        msg = str(e)
        if "[" not in msg:
            msg = f"[{current_step}] {msg}"
        return {
            "screenshot": saved_screenshot, 
            "step": current_step, 
            "error": msg,
            "extra_data": {}
        }

def _take_screenshot(page, exe_id: str, activity, screenshot_dir: Optional[Path]) -> Optional[str]:
    """Helper สำหรับถ่ายรูปหน้าจอ"""
    path_str = save_screenshot(
        page=page,
        exe_id=exe_id,
        activity_id=activity.id,
        screenshot_dir=screenshot_dir,
        suffix="general",
        full_page=False # สำหรับหน้า Login/Error มักไม่ต้องการ Full page เผื่อ Popup บัง
    )
    if path_str:
        pass
    return path_str


def _do_logout(page, n: int, total: int, exe_id: str) -> None:
    """Logout + จัดการ Popup ยืนยัน (ตกลง/ยืนยัน/Confirm)"""
    logout_clicked = False

    # 1. ลอง selector ตรงก่อน (เร็วและแม่นที่สุด)
    #    HTML จริง: <a href="...logout" class="btn logout-btn">LOGOUT</a>
    direct_selectors = [
        "a.logout-btn",              # class ตรง
        "a[href*='logout']",         # href มี logout
        ".logout-btn",               # class อย่างเดียว
        "a.btn.logout-btn",          # btn + logout-btn
    ]
    for sel in direct_selectors:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible(timeout=3000):
                btn.click(force=True, timeout=LOGOUT_CLICK_TIMEOUT_MS)
                logout_clicked = True
                status(n, total, "กด Logout สำเร็จ", exe_id)
                break
        except Exception:
            continue

    # 2. Fallback: ใช้ get_by_role + text
    if not logout_clicked:
        for text in ["LOGOUT", "ออกจากระบบ", "Log out", "Logout", "Sign out", "ออก"]:
            try:
                btn = (
                    page.get_by_role("link", name=text)
                    .or_(page.get_by_role("button", name=text))
                    .or_(page.get_by_text(text, exact=True))
                    .first
                )
                if btn.count() > 0:
                    btn.click(force=True, timeout=LOGOUT_CLICK_TIMEOUT_MS)
                    logout_clicked = True
                    break
            except Exception:
                continue

    # 3. Fallback สุดท้าย: navigate ตรงไป URL logout
    if not logout_clicked:
        try:
            # ดึง href จาก a.logout-btn (ถ้ามี) แล้ว navigate ตรง
            logout_href = page.locator("a.logout-btn, a[href*='logout']").first.get_attribute("href", timeout=3000)
            if logout_href:
                page.goto(logout_href, wait_until="domcontentloaded", timeout=15000)
                logout_clicked = True
                status(n, total, "Logout ผ่าน URL ตรง", exe_id)
        except:
            pass

    # 4. จัดการ Popup/Confirmation ที่อาจโผล่มาหลังกด Logout
    if logout_clicked:
        page.wait_for_timeout(1000)
        confirm_texts = ["ตกลง", "ยืนยัน", "Confirm", "OK", "ปิด", "ออกจากระบบ"]
        for ctext in confirm_texts:
            try:
                confirm_btn = page.locator(f"button:has-text('{ctext}'), a:has-text('{ctext}')").first
                if confirm_btn.count() > 0 and confirm_btn.is_visible():
                    confirm_btn.click(timeout=2000)
                    status(n, total, f"จัดการ Popup: {ctext}", exe_id)
                    page.wait_for_timeout(500)
            except Exception:
                continue
    else:
        status(n, total, "ไม่พบปุ่ม Logout (อาจอยู่นอกพื้นที่สำรวจ หรือ Logout ไปแล้ว)", exe_id)

def _short_error(e):
    return str(e).split("\n")[0][:100]
