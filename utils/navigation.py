# -*- coding: utf-8 -*-
"""
Utility สำหรับจัดการการเข้าถึงหน้าเว็บ (Navigation) ที่มีความทนทานสูง (Robust).
จัดการปัญหาหน้าเว็บค้าง, โหลดช้า, Gateway Error (504, 502) พร้อมระบบ Retry อัตโนมัติ.
"""

from typing import Optional, List
from utils.console import status
from core.delays import NAVIGATION_TIMEOUT_MS

def _short_error(e: Exception) -> str:
    s = str(e)
    return s[:100] + "..." if len(s) > 100 else s

def safe_goto(page, url: str, n: int, total: int, exe_id: str, 
              timeout: int = NAVIGATION_TIMEOUT_MS, 
              max_attempts: int = 3,
              wait_until: str = "domcontentloaded") -> Optional[object]:
    """
    ไปที่ URL พร้อมระบบ Retry (F5) เมื่อเจอ Error 504/502 หรือโหลดไม่ขึ้น.
    
    Args:
        page: Playwright Page object.
        url: URL ที่ต้องการไป.
        n, total, exe_id: สำหรับแสดงสถานะ (status).
        timeout: เวลาที่รอต่อการโหลดหนึ่งครั้ง.
        max_attempts: จำนวนครั้งที่จะลองใหม่.
        wait_until: สถานะการโหลดที่ต้องการรอ (load, domcontentloaded, networkidle).
        
    Returns:
        Response object หรือ None.
    """
    error_texts = [
        "504 Gateway Time-out", 
        "502 Bad Gateway", 
        "503 Service Unavailable", 
        "500 Internal Server Error",
        "Bad Gateway",
        "Service Temporarily Unavailable"
    ]
    
    for attempt in range(1, max_attempts + 1):
        try:
            if attempt > 1:
                status(n, total, f"พยายามโหลดหน้าใหม่ (F5) ครั้งที่ {attempt}/{max_attempts}...", exe_id)
            
            # ลองเปิดหน้าเว็บ
            response = page.goto(url, wait_until=wait_until, timeout=timeout)
            
            # 1. ตรวจสอบจาก HTTP Status Code
            if response and response.status >= 500:
                status(n, total, f"เซิร์ฟเวอร์ตอบกลับ Error {response.status}", exe_id)
                if attempt < max_attempts:
                    page.wait_for_timeout(3000)
                    continue
                else:
                    return response

            # 2. ตรวจสอบจากเนื้อหาหน้าเว็บ (กรณีเจอหน้า Error ของ Nginx/Cloudflare ตรงๆ)
            try:
                page.wait_for_timeout(1500)
                content = page.content()
                found_error = False
                for err in error_texts:
                    if err.lower() in content.lower():
                        status(n, total, f"ตรวจพบหน้า Error: {err}", exe_id)
                        found_error = True
                        break
                
                if found_error:
                    if attempt < max_attempts:
                        page.wait_for_timeout(3000)
                        continue
                    else:
                        break
            except Exception:
                pass
            
            # สำเร็จ: รอให้หน้าเว็บ settle อีกนิดถ้าเป็น wait_until แบบเร็ว
            if wait_until != "load":
                try:
                    page.wait_for_load_state("load", timeout=10000)
                except: pass
                
            return response
            
        except Exception as e:
            if attempt < max_attempts:
                status(n, total, f"หน้าเว็บค้างหรือโหลดช้า ({_short_error(e)}), ลองใหม่...", exe_id)
                page.wait_for_timeout(2000)
            else:
                status(n, total, f"❌ โหลดหน้าไม่สำเร็จหลังจากพยายาม {max_attempts} ครั้ง", exe_id)
                raise e
    return None

def wait_for_content(page, selector: str, n: int, total: int, exe_id: str, 
                     timeout_ms: int = 15000, 
                     max_retries: int = 2) -> bool:
    """
    รอให้ Element ที่สำคัญปรากฏ หากไม่มาจะลอง Refresh หน้าเว็บ.
    มีประโยชน์สำหรับหน้าเว็บที่เป็น SPA หรือโหลด Content ทีหลังซึ่งอาจค้างได้.
    """
    for i in range(max_retries + 1):
        try:
            page.wait_for_selector(selector, state="visible", timeout=timeout_ms)
            return True
        except Exception:
            if i < max_retries:
                status(n, total, f"คอนเทนต์ '{selector}' ไม่มา (ลองที่ {i+1}), กำลัง Refresh...", exe_id)
                page.reload(wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
            else:
                status(n, total, f"❌ ไม่สามารถโหลดคอนเทนต์ '{selector}' ได้", exe_id)
    return False
