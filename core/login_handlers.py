# -*- coding: utf-8 -*-
"""
Handlers สำหรับจัดการหน้า Login แต่ละแบบของ EXE.
แยกตามโครงสร้างหน้าเว็บ (Legacy vs Modern) เพื่อความแม่นยำในการหา Element.
"""

import random
from typing import Optional
from utils.agent import human_delay
from utils.console import status
from utils.preview import save_preview

def _type_humanly(page, element, text: str):
    """พิมพ์ทีละตัวด้วยความเร็วสุ่ม"""
    element.click()
    page.keyboard.type(text, delay=random.randint(80, 180))

def handle_login_any(page, exe_id: str, password: str, n: int, total: int, 
                     use_agent: bool = True, human_type: bool = False,
                     on_filled_callback=None) -> bool:
    """
    ตรวจสอบหน้าปัจจุบันว่าเป็นหน้า Login แบบไหน และเรียกใช้ handler ที่เหมาะสม.
    คืน True ถ้าเจอและทำ login สำเร็จ (หรือพยายามทำ).
    """
    url = page.url.lower()
    
    if "passport.exe.in.th" in url:
        return login_modern_passport(page, exe_id, password, n, total, use_agent, human_type, on_filled_callback)
    elif "accounts.exe.in.th" in url:
        return login_legacy_accounts(page, exe_id, password, n, total, use_agent, human_type, on_filled_callback)
    
    # ถ้าไม่ใช่ URL มาตรฐาน ลองใช้ Generic Handler (ชุดเดิม)
    return login_generic(page, exe_id, password, n, total, use_agent, human_type, on_filled_callback)

def login_modern_passport(page, exe_id: str, password: str, n: int, total: int, 
                          use_agent: bool, human_type: bool, on_filled_callback=None) -> bool:
    """Handler สำหรับหน้า https://passport.exe.in.th/exe-member/login"""
    try:
        # Modern passport: id="exeid" name="username" or name="exeid"
        username_field = page.locator('#exeid, input[name="username"], input[name="exeid"], input[placeholder*="EXE ID"]').first
        password_field = page.locator('#password, input[name="password"], input[type="password"]').first
        login_btn = page.locator('button[type="submit"].btn-primary, button[type="submit"], .btn-login').first
        
        username_field.wait_for(state="visible", timeout=10000)
        
        if use_agent: human_delay(0.2, 0.5)
        if human_type:
            _type_humanly(page, username_field, exe_id)
        else:
            username_field.fill(exe_id)
            
        if use_agent: human_delay(0.3, 0.6)
        
        if human_type:
            _type_humanly(page, password_field, password)
        else:
            password_field.fill(password)
            
        if use_agent: human_delay(0.4, 0.8)
        
        # Callback before clicking login (to capture filled ID/Pass for preview)
        if on_filled_callback:
            on_filled_callback(page)

        login_btn.click(force=True, timeout=10000)
        return True
    except Exception as e:
        status(n, total, f"Login Modern Error: {str(e)[:100]}", exe_id)
        return False

def login_legacy_accounts(page, exe_id: str, password: str, n: int, total: int, 
                          use_agent: bool, human_type: bool, on_filled_callback=None) -> bool:
    """Handler สำหรับหน้า https://accounts.exe.in.th/ (แบบ Return URL)"""
    try:
        # Legacy มักจะมีโครงสร้างง่ายๆ หรือใช้ id="username", id="password"
        # แต่บางทีก็เป็นช่องแรกสุดสีขาวๆ
        username_field = page.locator('#exeid, #username, input[name="exeid"], input[name="username"]').first
        if username_field.count() == 0:
            username_field = page.locator('input[type="text"]').first

        password_field = page.locator('#password, input[name="password"], input[type="password"]').first

        login_btn = page.locator('button[type="submit"].btn-primary, button[type="submit"], #btn-login').first
        
        username_field.wait_for(state="visible", timeout=10000)
        
        if use_agent: human_delay(0.2, 0.5)
        if human_type:
            _type_humanly(page, username_field, exe_id)
        else:
            username_field.fill(exe_id)
            
        if use_agent: human_delay(0.3, 0.6)
        
        if human_type:
            _type_humanly(page, password_field, password)
        else:
            password_field.fill(password)
            
        if use_agent: human_delay(0.4, 0.8)
        
        if on_filled_callback:
            on_filled_callback(page)

        login_btn.click(force=True, timeout=10000)
        return True
    except Exception as e:
        status(n, total, f"Login Legacy Error: {str(e)[:100]}", exe_id)
        return False

def login_generic(page, exe_id: str, password: str, n: int, total: int, 
                  use_agent: bool, human_type: bool, on_filled_callback=None) -> bool:
    """Fallback ในกรณีที่ไม่เจอ URL ที่ระบุไว้เฉพาะเจาะจง"""
    try:
        username_input = (
            page.get_by_placeholder("EXE ID")
            .or_(page.get_by_label("EXE ID"))
            .or_(page.locator('input[type="text"]').first)
        ).first
        
        password_input = (
            page.get_by_placeholder("รหัสผ่าน")
            .or_(page.get_by_label("รหัสผ่าน"))
            .or_(page.locator('input[type="password"]'))
        ).first
        
        login_btn = (
            page.get_by_role("button", name="เข้าสู่ระบบ")
            .or_(page.get_by_text("เข้าสู่ระบบ"))
            .first
        )
        
        username_input.wait_for(state="visible", timeout=10000)
        
        if human_type:
            _type_humanly(page, username_input, exe_id)
        else:
            username_input.fill(exe_id)
            
        if use_agent: human_delay(0.2, 0.5)
        
        if human_type:
            _type_humanly(page, password_input, password)
        else:
            password_input.fill(password)
            
        if use_agent: human_delay(0.2, 0.5)
        
        if on_filled_callback:
            on_filled_callback(page)

        login_btn.click(force=True, timeout=10000)
        return True
    except Exception as e:
        status(n, total, f"Login Generic Error: {str(e)[:100]}", exe_id)
        return False

def check_login_error_any(page) -> Optional[str]:
    """ตรวจสอบว่ามี Error Message ปรากฏขึ้นหลังกด Login หรือไม่"""
    error_texts = [
        "EXE ID หรือ รหัสผ่าน ไม่ถูกต้อง",
        "ไม่ถูกต้องกรุณาลองใหม่อีกครั้ง",
        "Invalid username or password",
        "ไอดีหรือรหัสผ่านไม่ถูกต้อง"
    ]
    # รอซักครู่เผื่อเน็ตช้า
    try:
        page.wait_for_timeout(1500)
        for text in error_texts:
            loc = page.get_by_text(text).first
            if loc.count() > 0 and loc.is_visible():
                return "Fail ตั้งแต่ขั้นตอน login"
    except:
        pass
    return None
