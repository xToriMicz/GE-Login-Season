# -*- coding: utf-8 -*-
"""
Retry logic สำหรับจัดการการ Retry บัญชีที่ล้มเหลว.
Single Responsibility: ตัดสินใจว่าควร retry หรือไม่ และจัดการ loop
"""

import time
from typing import Callable, Dict, Any, Optional

# Error messages ที่ไม่ควร retry (เพราะรหัสผิดจริง)
NON_RETRYABLE_ERRORS = [
    "รหัสผ่าน ไม่ถูกต้อง",
    "รหัสผิด",
    "Invalid username or password",
    "ไม่ถูกต้อง",
    "Fail ตั้งแต่ขั้นตอน login",
]

def should_retry(error_message: str) -> bool:
    """
    ตรวจสอบว่า error นี้ควร retry ไหม.

    Returns:
        True ถ้าควร retry (เช่น timeout, network)
        False ถ้าไม่ควร retry (เช่น รหัสผิด)
    """
    if not error_message:
        return False

    error_lower = error_message.lower()
    for non_retry in NON_RETRYABLE_ERRORS:
        if non_retry.lower() in error_lower:
            return False

    return True


def get_retry_delay(error_message: str) -> int:
    """คืนเวลา delay (วินาที) ตาม error type — server ล่มรอนานกว่า"""
    if not error_message:
        return 3
    err = error_message.lower()
    # IP blocked / rate limited — รอ 120 วินาที
    if any(x in err for x in ["403 forbidden", "429 too many", "access denied",
                                "you have been blocked", "rate limit", "ip block"]):
        return 120
    # Server ล่ม / connection error — รอ 30-60 วินาที
    if any(x in err for x in ["connection_timed_out", "server ล่ม", "502", "504",
                                "connection_refused", "gateway"]):
        return 45
    # Timeout ทั่วไป — รอ 10 วินาที
    if any(x in err for x in ["timeout", "timed out", "ช้า"]):
        return 10
    return 3


def run_with_retry(
    run_func: Callable[[], Dict[str, Any]],
    max_retries: int,
    retry_delay_seconds: float = 3.0,
    on_retry: Optional[Callable[[int, str], None]] = None,
    on_skip_retry: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    รัน function พร้อม retry logic.
    
    Args:
        run_func: ฟังก์ชันที่จะรัน ต้องคืน dict ที่มี "error" key (None ถ้าสำเร็จ)
        max_retries: จำนวนครั้งที่จะ retry (0 = ไม่ retry เลย)
        retry_delay_seconds: รอกี่วินาทีก่อน retry
        on_retry: callback(attempt, error) เรียกก่อน retry
        on_skip_retry: callback(error) เรียกเมื่อ error ไม่ควร retry
        
    Returns:
        ผลลัพธ์จาก run_func ครั้งสุดท้าย
    """
    last_result = None
    
    for attempt in range(max_retries + 1):  # +1 เพราะครั้งแรกไม่นับ retry
        result = run_func()
        last_result = result
        
        # สำเร็จ - หยุดเลย
        if not result.get("error"):
            return result
        
        error_msg = result.get("error", "")
        
        # ตรวจสอบว่าควร retry ไหม
        if not should_retry(error_msg):
            if on_skip_retry:
                on_skip_retry(error_msg)
            return result
        
        # ยังมี attempt เหลือ -> retry
        if attempt < max_retries:
            if on_retry:
                on_retry(attempt + 1, error_msg)
            time.sleep(retry_delay_seconds)
        # หมด attempt แล้ว -> return ผลสุดท้าย
    
    return last_result
