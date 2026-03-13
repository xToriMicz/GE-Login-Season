# -*- coding: utf-8 -*-
"""
โหลด cookies จากเบราว์เซอร์หลัก (Chrome) ของเครื่อง — ใช้กับ Cloudflare ที่ต้องใช้ค่า cookie จากเบราว์เซอร์ที่เปิดอยู่
หมายเหตุ: บน Windows ถ้า Chrome เปิดอยู่ ไฟล์ cookies อาจถูกล็อก — แนะนำปิด Chrome ก่อน หรือ export cookies เองแล้วใช้ --cookies
"""

from typing import List, Optional


def get_chrome_cookies_for_playwright(domains: Optional[List[str]] = None) -> List[dict]:
    """
    อ่าน cookies จาก Chrome (เบราว์เซอร์หลัก) สำหรับ domain ที่กำหนด แล้วแปลงเป็นรูปแบบที่ Playwright ใช้
    domains: เช่น [".exe.in.th", "itemcode.exe.in.th"] — ถ้า None ใช้ .exe.in.th
    คืน: list of dict แต่ละตัวมี name, value, domain, path, secure, sameSite [, expires]
    ถ้าอ่านไม่ได้ (เช่น Chrome เปิดอยู่บน Windows) คืน []
    """
    if domains is None:
        domains = [".exe.in.th"]
    try:
        import browser_cookie3
    except ImportError:
        return []

    all_cookies = []
    seen = set()

    for domain in domains:
        try:
            cj = browser_cookie3.chrome(domain_name=domain)
        except Exception:
            continue
        for c in cj:
            key = (c.name, c.domain, c.path)
            if key in seen:
                continue
            seen.add(key)
            item = {
                "name": c.name,
                "value": c.value,
                "domain": getattr(c, "domain", "") or ".exe.in.th",
                "path": getattr(c, "path", None) or "/",
                "secure": getattr(c, "secure", True),
                "sameSite": "Lax",
            }
            if getattr(c, "expires", None):
                try:
                    item["expires"] = float(c.expires)
                except (TypeError, ValueError):
                    pass
            all_cookies.append(item)

    return all_cookies
