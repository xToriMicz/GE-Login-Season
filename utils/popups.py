# -*- coding: utf-8 -*-
"""
Popup State Detection & Handling Module
========================================
ตรวจจับและจัดการ Popup, Modal, และ Overlay ทุกชนิดในหน้ากิจกรรม

หลักการ: "Overlay-First" — ตรวจว่ามี popup container จริงก่อน
แล้วค่อยกดปุ่มปิดเฉพาะภายใน container นั้น ไม่กดปุ่มหน้าเว็บปกติ
"""

from utils.console import status


# ─── Popup Container Selectors ──────────────────────────────────────
# ใช้ตรวจว่ามี popup/modal/overlay ปรากฏอยู่จริงไหม
_POPUP_CONTAINERS = [
    # SweetAlert 2
    {"selector": ".swal2-container", "type": "swal2"},
    {"selector": ".swal2-popup",     "type": "swal2"},
    # Bootstrap Modal
    {"selector": ".modal.show",      "type": "modal"},
    {"selector": ".modal.fade.show", "type": "modal"},
    # Custom Popup / Overlay ทั่วไป
    {"selector": ".popup-overlay",   "type": "overlay"},
    {"selector": ".popup.show",      "type": "overlay"},
    {"selector": ".overlay.active",  "type": "overlay"},
]

# ─── Close Button Selectors (ใช้ในกรอบ popup เท่านั้น) ─────────────
_CLOSE_BUTTONS_IN_POPUP = [
    "button:has-text('ปิด')",
    "a:has-text('ปิด')",
    "button:has-text('ตกลง')",
    "a:has-text('ตกลง')",
    "button:has-text('ยืนยัน')",
    "a:has-text('ยืนยัน')",
    "button:has-text('CLOSE')",
    "button:has-text('Close')",
    "button:has-text('OK')",
    "button:has-text('Confirm')",
    ".swal2-confirm",
    ".modal-header .close",
    ".modal-footer button",
    "button[class*='close']",
    "button[class*='btn-close']",
]

# ─── Standalone close selectors (ไม่ต้องมี container ก็กดได้) ──────
# สำหรับ SweetAlert ที่อยู่นอก modal container ทั่วไป
_STANDALONE_CLOSE = [
    ".swal2-confirm",
    ".swal2-close",
]


def is_popup_visible(page) -> dict | None:
    """
    ตรวจว่ามี popup/modal/overlay ปรากฏอยู่จริงไหม

    Returns:
        dict {"type": str, "container": Locator} ถ้าเจอ popup
        None ถ้าไม่มี popup
    """
    for cfg in _POPUP_CONTAINERS:
        try:
            el = page.locator(cfg["selector"]).first
            if el.count() > 0 and el.is_visible(timeout=500):
                return {"type": cfg["type"], "container": el}
        except:
            continue
    return None


def _click_close_in_container(page, container, timeout_ms=1000) -> bool:
    """หาปุ่มปิดภายใน popup container แล้วกด"""
    for sel in _CLOSE_BUTTONS_IN_POPUP:
        try:
            btn = container.locator(sel).first
            if btn.count() > 0 and btn.is_visible(timeout=timeout_ms):
                btn.click(force=True)
                page.wait_for_timeout(800)
                return True
        except:
            continue
    return False


def _click_standalone_close(page) -> bool:
    """กดปุ่ม SweetAlert / standalone close ที่ไม่ต้องหา container"""
    for sel in _STANDALONE_CLOSE:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible(timeout=500):
                btn.click(force=True)
                page.wait_for_timeout(800)
                return True
        except:
            continue
    return False


def wait_and_close_popup(page, timeout_ms: int = 5000, n: int = 0, total: int = 0, exe_id: str = "") -> bool:
    """
    รอ popup ปรากฏภายใน timeout → พอเจอ → กดปิด

    ใช้หลังกดปุ่มที่คาดว่าจะมี popup ตามมา (เช่น OPEN กล่อง, ยิง Arrow)
    คืน True ถ้าปิด popup ได้สำเร็จ
    """
    # รอจนเจอ popup container
    elapsed = 0
    step = 500
    popup_info = None

    while elapsed < timeout_ms:
        popup_info = is_popup_visible(page)
        if popup_info:
            break
        # ลอง standalone (SweetAlert อาจไม่มี container wrapper)
        if _click_standalone_close(page):
            return True
        page.wait_for_timeout(step)
        elapsed += step

    if not popup_info:
        return False

    # เจอ popup → กดปุ่มปิดภายใน container
    closed = _click_close_in_container(page, popup_info["container"])
    if not closed:
        # Fallback: ลอง standalone
        closed = _click_standalone_close(page)

    return closed


def clear_any_popups(page, n: int = 0, total: int = 0, exe_id: str = "") -> bool:
    """
    ตรวจสอบและปิด Popup ทุกชนิดที่ขวางหน้าจอ (backward compatible API)

    หลักการใหม่: ตรวจ overlay/container ก่อน → กดปุ่มในกรอบ popup เท่านั้น
    ไม่กดปุ่ม page content ปกติ

    คืนค่า True หากมีการปิด Popup ไปอย่างน้อยหนึ่งครั้ง
    """
    found_and_closed = False

    try:
        # ลองปิดสูงสุด 3 ชั้น เผื่อมี Popup ซ้อน Popup
        for _ in range(3):
            closed_in_round = False

            # 1. ตรวจว่ามี popup container จริงไหม
            popup_info = is_popup_visible(page)
            if popup_info:
                # กดปุ่มปิดภายใน container
                if _click_close_in_container(page, popup_info["container"]):
                    closed_in_round = True
                    found_and_closed = True

            # 2. ถ้าไม่เจอ container — ลอง standalone (SweetAlert)
            if not closed_in_round:
                if _click_standalone_close(page):
                    closed_in_round = True
                    found_and_closed = True

            if not closed_in_round:
                break  # ไม่มี popup แล้ว

    except Exception:
        pass

    return found_and_closed
