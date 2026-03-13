# -*- coding: utf-8 -*-
"""
Preview utility สำหรับบันทึก screenshot แบบย่อขนาดระหว่าง automation.
ใช้สำหรับแสดงใน Preview Tab ของ UI
"""

from pathlib import Path

# โฟลเดอร์เก็บ preview image
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PREVIEW_DIR = PROJECT_ROOT / ".preview"
PREVIEW_FILE = PREVIEW_DIR / "current.png"

def save_preview(page, quality: int = 50) -> bool:
    """
    บันทึก screenshot ปัจจุบันลงไฟล์ preview.
    
    Args:
        page: Playwright Page object
        quality: คุณภาพรูป (1-100) ยิ่งต่ำยิ่งเบา
        
    Returns:
        True ถ้าบันทึกสำเร็จ
    """
    try:
        PREVIEW_DIR.mkdir(exist_ok=True)
        
        # Playwright screenshot with scale to reduce size
        page.screenshot(
            path=str(PREVIEW_FILE),
            type="png",
            scale="css",  # ใช้ CSS scale (เบากว่า device scale)
        )
        return True
    except Exception:
        return False


def clear_preview():
    """ลบไฟล์ preview เมื่อหยุดทำงาน"""
    try:
        if PREVIEW_FILE.exists():
            PREVIEW_FILE.unlink()
    except Exception:
        pass
