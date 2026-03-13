# -*- coding: utf-8 -*-
"""Entry point เมื่อรัน python -m ui หรือ GE_Login.exe"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def check_playwright_browsers():
    """ตรวจสอบและติดตั้ง Playwright browsers ถ้าจำเป็น"""
    marker_file = PROJECT_ROOT / ".browsers_installed"
    
    if marker_file.exists():
        return True  # เคยติดตั้งแล้ว
    
    print("[System] ตรวจสอบ Playwright browsers...")
    
    try:
        # ลองเปิด browser ดูว่ามีไหม
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        
        # ถ้าเปิดได้ สร้าง marker
        marker_file.touch()
        return True
    except Exception:
        return False


def install_playwright_browsers():
    """ติดตั้ง Playwright chromium browser"""
    print()
    print("=" * 50)
    print("   กำลังติดตั้ง Browser สำหรับ Bot...")
    print("   (รอสักครู่ ประมาณ 1-2 นาที)")
    print("=" * 50)
    print()
    
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        
        # สร้าง marker file
        marker_file = PROJECT_ROOT / ".browsers_installed"
        marker_file.touch()
        
        print()
        print("✅ ติดตั้ง Browser เรียบร้อยแล้ว!")
        return True
    except Exception as e:
        print(f"❌ ติดตั้งไม่สำเร็จ: {e}")
        return False


def main():
    # Handle --install-browsers flag
    if "--install-browsers" in sys.argv:
        success = install_playwright_browsers()
        sys.exit(0 if success else 1)
    
    # ตรวจสอบ browser ครั้งแรก
    if not check_playwright_browsers():
        print("[System] ไม่พบ Browser, กำลังติดตั้ง...")
        install_playwright_browsers()
    
    # เปิด UI
    from .main_window import main as run_ui
    run_ui()


if __name__ == "__main__":
    main()
