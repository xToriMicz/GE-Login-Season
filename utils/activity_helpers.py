# -*- coding: utf-8 -*-
"""
Reusable building blocks สำหรับทุก activity.
แทนที่จะ copy-paste logic เดิมๆ ทุกกิจกรรม — import จากที่นี่แทน

ใช้งาน:
    from utils.activity_helpers import verify_page, read_points, click_loop, safe_reload
"""

import random
import re

from utils.console import status
from utils.agent import bypass_cloudflare
from utils.navigation import wait_for_content, safe_goto
from utils.popups import clear_any_popups, wait_and_close_popup


# ─── Low-level checks ─────────────────────────────────────────────


def is_page_error(page) -> bool:
    """เช็คว่าหน้าเว็บแสดง Error Page หรือไม่ (502, 504, blank, etc.)"""
    try:
        content = page.content()
        error_texts = [
            "504 gateway", "502 bad gateway", "503 service",
            "500 internal", "bad gateway", "service temporarily unavailable",
            "ERR_CONNECTION", "ERR_TIMED_OUT", "ERR_NAME_NOT_RESOLVED",
        ]
        content_lower = content.lower()
        for err in error_texts:
            if err.lower() in content_lower:
                return True
        # หน้าว่างเปล่า (กรณี crash หรือ blank page)
        if len(content.strip()) < 100:
            return True
    except:
        return True
    return False


def check_login(page) -> bool:
    """เช็คสถานะล็อกอินในหน้ากิจกรรม (อิงจาก .id-name หรือ .logout-btn)"""
    try:
        profile = page.locator(".id-name, .logout-btn").first
        return profile.count() > 0 and profile.is_visible()
    except:
        return False


def get_logged_in_id(page) -> str:
    """อ่าน EXE ID ที่ล็อกอินอยู่จาก .id-name"""
    try:
        text = page.locator(".id-name").first.inner_text(timeout=5000)
        match = re.search(r"EXE\s*ID\s*:\s*(\S+)", text, re.IGNORECASE)
        return match.group(1).strip() if match else text.strip()
    except:
        return ""


# ─── Point reading ─────────────────────────────────────────────────


def read_points(page, selector: str, timeout_ms: int = 5000) -> int:
    """
    อ่านตัวเลขจาก selector (filter digits).
    ใช้ได้กับทุก element ที่แสดงตัวเลข เช่น .point-counter, .love-energy, .bonus-point
    คืน 0 ถ้าอ่านไม่ได้
    """
    try:
        el = page.locator(selector).first
        if el.count() == 0:
            return 0
        text = el.inner_text(timeout=timeout_ms)
        return int("".join(filter(str.isdigit, text)) or "0")
    except:
        return 0


# ─── Page reload ───────────────────────────────────────────────────


def safe_reload(
    page, n, total, exe_id,
    activity_url=None,
    url_marker=None,
    content_selector=".id-name, .logout-btn",
    max_attempts=3,
) -> bool:
    """
    Reload หน้าเว็บอย่างปลอดภัย พร้อมจัดการ Error/Timeout/Cloudflare.
    ถ้าอยู่ผิด URL จะ navigate ไปหน้าที่ถูกต้องแทน reload.
    คืนค่า True ถ้าหน้าโหลดกลับมามีเนื้อหาปกติ
    """
    for attempt in range(1, max_attempts + 1):
        try:
            if attempt > 1:
                status(n, total, f"⚠️ หน้าเว็บมีปัญหา พยายามโหลดใหม่ครั้งที่ {attempt}/{max_attempts}...", exe_id)
                page.wait_for_timeout(random.randint(3000, 5000))

            # ถ้าอยู่ผิด URL ให้ navigate ไปหน้าที่ถูกต้อง
            current_url = page.url.lower()
            if activity_url and url_marker and url_marker not in current_url:
                status(n, total, "🔗 URL ผิดหน้า กำลัง Navigate กลับ...", exe_id)
                safe_goto(page, activity_url, n, total, exe_id)
            else:
                page.reload(wait_until="domcontentloaded", timeout=30000)

            page.wait_for_timeout(2000)

            if is_page_error(page):
                if attempt < max_attempts:
                    continue
                else:
                    status(n, total, f"❌ หน้าเว็บยังเป็น Error หลังจากลอง {max_attempts} ครั้ง", exe_id)
                    return False

            # Bypass Cloudflare ถ้ามี
            bypass_cloudflare(page, n, total, exe_id, status)

            # รอ Content สำคัญให้ปรากฏ
            if wait_for_content(page, content_selector, n, total, exe_id,
                                timeout_ms=15000, max_retries=1):
                return True

            if attempt < max_attempts:
                continue

        except Exception as e:
            if attempt < max_attempts:
                status(n, total, f"⚠️ Reload ผิดพลาด: {str(e)[:50]}, ลองอีกครั้ง...", exe_id)
            else:
                status(n, total, f"❌ Reload ไม่สำเร็จ: {str(e)[:50]}", exe_id)

    return False


# ─── Page verification ─────────────────────────────────────────────


def verify_page(
    page, activity, n, total, exe_id,
    url_marker=None,
    content_selector=".id-name, .logout-btn",
) -> bool:
    """
    Verify ว่าหน้าเว็บพร้อมทำงาน:
      1. เช็ค URL ตรงกับกิจกรรม (navigate ถ้าผิด)
      2. Bypass Cloudflare
      3. เช็ค Error Page → safe_reload
      4. รอ content สำคัญ
      5. เช็คล็อกอิน
      6. เช็ค EXE ID ตรงกัน
    คืน True ถ้า verify ผ่านทั้งหมด
    """
    # 1. เช็ค URL
    if url_marker:
        current_url = page.url.lower()
        if url_marker not in current_url:
            status(n, total, f"URL ผิดหน้า กำลังนำทางไปหน้ากิจกรรม...", exe_id)
            try:
                safe_goto(page, activity.url, n, total, exe_id)
                page.wait_for_timeout(2000)
            except Exception as e:
                status(n, total, f"⚠️ Navigate ไปหน้ากิจกรรมไม่ได้: {str(e)[:50]}", exe_id)
                return False

    # 2. Bypass Cloudflare
    status(n, total, "ตรวจสอบสถานะและข้าม Cloudflare...", exe_id)
    bypass_cloudflare(page, n, total, exe_id, status)

    # 3. เช็ค Error Page
    if is_page_error(page):
        status(n, total, "⚠️ หน้าเว็บเป็น Error Page พยายามโหลดใหม่...", exe_id)
        if not safe_reload(page, n, total, exe_id,
                           activity_url=activity.url, url_marker=url_marker,
                           content_selector=content_selector):
            return False

    # 4. รอ content
    if not wait_for_content(page, content_selector, n, total, exe_id, timeout_ms=15000):
        status(n, total, "⚠️ ไม่พบ element ล็อกอิน ลอง Reload หน้า...", exe_id)
        if not safe_reload(page, n, total, exe_id,
                           activity_url=activity.url, url_marker=url_marker,
                           content_selector=content_selector):
            return False

    # 5. เช็คล็อกอิน
    if not check_login(page):
        status(n, total, "❌ ไม่พบสถานะล็อกอิน", exe_id)
        return False

    # 6. เช็ค EXE ID
    logged_id = get_logged_in_id(page)
    if logged_id:
        if logged_id.lower() != exe_id.lower():
            status(n, total, f"⚠️ ไอดีไม่ตรง! เว็บ={logged_id} vs รัน={exe_id}", exe_id)
        else:
            status(n, total, f"✅ ไอดีตรงกัน: {logged_id}", exe_id)
    else:
        status(n, total, "⚠️ อ่านไอดีจากหน้าเว็บไม่ได้", exe_id)

    return True


# ─── Popup dismiss ─────────────────────────────────────────────────


def dismiss_popup(page, n, total, exe_id, timeout_ms=5000) -> bool:
    """
    รอ popup (Swal/Modal) แล้วกดปิด.
    ใช้หลังกดปุ่มที่คาดว่าจะมี popup ตามมา (เช่น กดยิง, กดเปิดกล่อง)
    """
    closed = wait_and_close_popup(page, timeout_ms=timeout_ms, n=n, total=total, exe_id=exe_id)
    if not closed:
        closed = clear_any_popups(page, n=n, total=total, exe_id=exe_id)
    return closed


# ─── Button click helpers ──────────────────────────────────────────


def _is_btn_disabled(page, selector: str) -> bool:
    """เช็คว่าปุ่มนั้น disabled หรือถูก greyscale อยู่หรือไม่"""
    try:
        btn = page.locator(selector).first
        if btn.count() == 0:
            return True
        if btn.is_disabled():
            return True
        cls = btn.get_attribute("class") or ""
        if "close-btn" in cls:
            return True
        return False
    except:
        return True


def _click_btn(page, selector, n, total, exe_id, animation_ms=(1200, 1800), swal_timeout_ms=6000) -> bool:
    """
    คลิกปุ่มแล้วรอ animation + dismiss popup.
    คืน True ถ้าคลิกสำเร็จ
    """
    if _is_btn_disabled(page, selector):
        return False

    try:
        btn = page.locator(selector).first
        if not (btn.count() > 0 and btn.is_visible(timeout=3000)):
            return False

        btn.click(force=True)
        page.wait_for_timeout(random.randint(*animation_ms))

        dismissed = dismiss_popup(page, n, total, exe_id, timeout_ms=swal_timeout_ms)
        if not dismissed:
            status(n, total, f"⚠️ ปิด Popup ไม่ได้หลังกด {selector}", exe_id)

        page.wait_for_timeout(random.randint(500, 1000))
        return True

    except Exception as e:
        status(n, total, f"⚠️ คลิก {selector} ไม่ได้: {str(e)[:50]}", exe_id)
        return False


# ─── Click loop ────────────────────────────────────────────────────


def click_loop(
    page, btn_selector, point_selector, n, total, exe_id,
    max_rounds=30,
    threshold_x10=10,
    btn_x10=None,
    refresh_selector=None,
    animation_ms=(1200, 1800),
    swal_timeout_ms=6000,
) -> int:
    """
    วนกดปุ่มจนแต้มหมด.

    Args:
        btn_selector: ปุ่มหลัก x1 (เช่น "#free-btn")
        point_selector: อ่านแต้มคงเหลือ (เช่น ".point-counter")
        btn_x10: ปุ่ม x10 (optional, เช่น "#freex10-btn")
        threshold_x10: ใช้ x10 เมื่อแต้ม >= ค่านี้
        refresh_selector: ปุ่ม refresh ก่อนอ่านแต้ม (optional, เช่น "button.btn-refresh")
        animation_ms: (min, max) delay หลัง click (ms)
        swal_timeout_ms: timeout รอ popup หลังกด

    Returns:
        total_clicks (int) — จำนวนครั้งที่กดสำเร็จ
    """
    def _refresh_and_read():
        """กดปุ่ม refresh (ถ้ามี) แล้วอ่านแต้ม"""
        if refresh_selector:
            try:
                btn = page.locator(refresh_selector).first
                if btn.count() > 0 and btn.is_visible(timeout=3000):
                    btn.click(force=True)
                    page.wait_for_timeout(random.randint(1500, 2500))
            except:
                pass
        return read_points(page, point_selector)

    points = _refresh_and_read()
    status(n, total, f"🎯 แต้ม = {points} → เริ่มกด!", exe_id)

    total_clicks = 0
    rounds = 0

    while points > 0 and rounds < max_rounds:
        rounds += 1

        # เลือกปุ่ม x10 หรือ x1
        if btn_x10 and points >= threshold_x10:
            use_selector = btn_x10
            shot_count = 10
            shot_label = "x10"
        else:
            use_selector = btn_selector
            shot_count = 1
            shot_label = "x1"

        status(n, total, f"🎯 รอบ {rounds}: กด {shot_label} (เหลือ {points})...", exe_id)

        clicked = _click_btn(page, use_selector, n, total, exe_id,
                             animation_ms=animation_ms, swal_timeout_ms=swal_timeout_ms)

        if not clicked:
            # ลอง refresh แล้วอ่านอีกรอบ
            status(n, total, f"⚠️ กดปุ่ม {use_selector} ไม่ได้ ลอง Refresh...", exe_id)
            points = _refresh_and_read()
            if points <= 0:
                status(n, total, "✅ แต้มหมดแล้ว (ปุ่ม disabled)", exe_id)
                break
            # ถ้าใช้ x10 ไม่ได้ ลอง x1 แทน
            if use_selector == btn_x10:
                status(n, total, "🔄 ลองกดปุ่ม x1 แทน...", exe_id)
                clicked = _click_btn(page, btn_selector, n, total, exe_id,
                                     animation_ms=animation_ms, swal_timeout_ms=swal_timeout_ms)
                if clicked:
                    shot_count = 1
                else:
                    status(n, total, "❌ กดปุ่มไม่ได้ทั้ง 2 ปุ่ม หยุด", exe_id)
                    break
            else:
                status(n, total, "❌ กดปุ่มไม่ได้ หยุด", exe_id)
                break

        total_clicks += shot_count

        # อ่านแต้มใหม่
        points = _refresh_and_read()
        status(n, total, f"   → กดแล้ว {total_clicks} ครั้ง | เหลือ = {points}", exe_id)

    if points <= 0:
        status(n, total, f"✅ กดจบ! รวม {total_clicks} ครั้ง (แต้ม = 0)", exe_id)
    else:
        status(n, total, f"⚠️ หยุดกด (รอบ {rounds}): รวม {total_clicks} ครั้ง, เหลือ {points}", exe_id)

    return total_clicks
