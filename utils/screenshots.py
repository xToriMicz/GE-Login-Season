# -*- coding: utf-8 -*-
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

def save_screenshot(
    page,
    exe_id: str,
    activity_id: str,
    screenshot_dir: Optional[Union[str, Path]] = None,
    suffix: str = "",
    full_page: bool = False,
    locator = None
) -> Optional[str]:
    """
    บันทึกภาพหน้าจอลงในโครงสร้างโฟลเดอร์มาตรฐาน:
    screenshot_dir / activity_id / YYYY-MM-DD / {exe_id}_{suffix}.png
    """
    if not screenshot_dir:
        return None
        
    try:
        base_dir = Path(screenshot_dir)
        date_str = datetime.now().strftime("%Y-%m-%d")
        ts = datetime.now().strftime("%H%M%S")
        
        # จัดการโฟลเดอร์ย่อย (แยกตาม debug หรือไม่)
        # ถ้า suffix มีคำว่า debug ให้นำไปไว้ในโฟลเดอร์ debug ย่อย
        sub_folder = ""
        if "debug" in suffix.lower():
            sub_folder = "debug"
        
        target_dir = base_dir / activity_id / date_str
        if sub_folder:
            target_dir = target_dir / sub_folder
            
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # คลีนชื่อไฟล์ (ทำลายอักขระพิเศษ)
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in exe_id)
        
        filename = f"{safe_id}_{ts}"
        if suffix:
            filename += f"_{suffix}"
        filename += ".png"
        
        save_path = target_dir / filename
        
        # ถ่ายรูป (รองรับทั้ง Element Locator และทั้งหน้า)
        if locator:
            locator.screenshot(path=str(save_path))
        else:
            page.screenshot(path=str(save_path), full_page=full_page)
            
        return str(save_path.absolute())
    except Exception as e:
        # พยายามแจ้งเตือนผ่าน print ในระดับล่าง ถ้า status(..) เข้าไม่ถึง
        print(f"Warning [save_screenshot]: {str(e)[:100]}")
        return None
