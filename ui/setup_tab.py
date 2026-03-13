# -*- coding: utf-8 -*-
"""
Setup Tab — ตรวจสอบและติดตั้ง dependencies สำหรับ UI
"""

import subprocess
import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path

from ui.styles import FG_SUCCESS, FG_ERROR, FG_DIM, FG_ACCENT

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def check_python_packages():
    """ตรวจสอบ Python packages ที่จำเป็น"""
    packages = {
        "playwright": False,
        "browser_cookie3": False,
        "PIL": False,  # Pillow
    }
    
    try:
        import playwright
        packages["playwright"] = True
    except ImportError:
        pass
    
    try:
        import browser_cookie3
        packages["browser_cookie3"] = True
    except ImportError:
        pass
    
    try:
        from PIL import Image
        packages["PIL"] = True
    except ImportError:
        pass
    
    return packages


def check_playwright_browser():
    """ตรวจสอบว่ามี Chromium browser หรือไม่"""
    marker_file = PROJECT_ROOT / ".browsers_installed"
    if marker_file.exists():
        return True
    
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        marker_file.touch()
        return True
    except Exception:
        return False


def build_tab_setup(window, parent):
    """สร้าง Tab Setup สำหรับตรวจสอบ dependencies"""
    parent.configure(style="Card.TFrame")
    ttk.Label(parent, text=" ⚙️ Setup & Installation ", style="Section.TLabel").pack(fill=tk.X, pady=(0, 10))
    
    # Status Frame
    status_frame = ttk.LabelFrame(parent, text=" สถานะการติดตั้ง ", padding=10)
    status_frame.pack(fill=tk.X, pady=5)
    
    # Store status labels for updating
    window._setup_status_labels = {}
    
    items = [
        ("Python", "python_ok", True),  # Always True if UI is running
        ("Playwright", "playwright_ok", None),
        ("Browser Cookie3", "browser_cookie3_ok", None),
        ("Pillow (Preview)", "pillow_ok", None),
        ("Chromium Browser", "chromium_ok", None),
    ]
    
    for name, key, initial in items:
        row = ttk.Frame(status_frame)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text=f"  {name}:", width=20).pack(side=tk.LEFT)
        lbl = ttk.Label(row, text="⏳ กำลังตรวจสอบ..." if initial is None else "✅ พร้อม", 
                       foreground=FG_DIM if initial is None else FG_SUCCESS)
        lbl.pack(side=tk.LEFT)
        window._setup_status_labels[key] = lbl
    
    # Buttons Frame
    btn_frame = ttk.Frame(parent)
    btn_frame.pack(fill=tk.X, pady=15)
    
    window._btn_check = ttk.Button(btn_frame, text="🔍 ตรวจสอบใหม่", 
                                   command=lambda: _refresh_status(window))
    window._btn_check.pack(side=tk.LEFT, padx=5)
    
    window._btn_install = ttk.Button(btn_frame, text="📦 Install / Re-install All (แนะนำ)", 
                                     command=lambda: _install_all(window))
    window._btn_install.pack(side=tk.LEFT, padx=5)
    
    # Highlight the recommended button
    window._btn_install.focus_set()
    
    window._btn_install_browser = ttk.Button(btn_frame, text="🌐 Install Browser Only", 
                                             command=lambda: _install_browser(window))
    window._btn_install_browser.pack(side=tk.LEFT, padx=5)
    
    # Log area
    ttk.Label(parent, text="Log:", foreground=FG_DIM).pack(anchor=tk.W, pady=(10, 2))
    
    # Use Segoe UI or Tahoma for Thai support in Text widget
    log_font = ("Consolas", 9) 
    if sys.platform == "win32":
        log_font = ("Tahoma", 9)

    window._setup_log = tk.Text(parent, height=8, bg="#1a1a2e", fg="white", 
                                font=log_font, state=tk.DISABLED)
    window._setup_log.pack(fill=tk.BOTH, expand=True, pady=5)
    
    # Initial check (delayed)
    parent.after(500, lambda: _refresh_status(window))


def _log_setup(window, text):
    """เพิ่มข้อความลง log"""
    if hasattr(window, '_setup_log'):
        window._setup_log.config(state=tk.NORMAL)
        window._setup_log.insert(tk.END, text + "\n")
        window._setup_log.see(tk.END)
        window._setup_log.config(state=tk.DISABLED)
        window.root.update()


def _update_status(window, key, ok, text=None):
    """อัปเดตสถานะ"""
    if key in window._setup_status_labels:
        lbl = window._setup_status_labels[key]
        if ok:
            lbl.config(text=text or "✅ พร้อม", foreground=FG_SUCCESS)
        else:
            lbl.config(text=text or "❌ ยังไม่ติดตั้ง", foreground=FG_ERROR)


def _refresh_status(window):
    """ตรวจสอบสถานะทั้งหมดใหม่"""
    _log_setup(window, "[Check] กำลังตรวจสอบ dependencies...")
    
    # Check Python packages
    packages = check_python_packages()
    _update_status(window, "playwright_ok", packages["playwright"])
    _update_status(window, "browser_cookie3_ok", packages["browser_cookie3"])
    _update_status(window, "pillow_ok", packages["PIL"])
    
    # Check browser
    browser_ok = check_playwright_browser()
    _update_status(window, "chromium_ok", browser_ok)
    
    all_ok = all(packages.values()) and browser_ok
    if all_ok:
        _log_setup(window, "[Check] ✅ ทุกอย่างพร้อมใช้งาน!")
    else:
        missing = [k for k, v in packages.items() if not v]
        if not browser_ok:
            missing.append("Chromium")
        _log_setup(window, f"[Check] ⚠️ ยังขาด: {', '.join(missing)}")


def _install_all(window):
    """ติดตั้งทุกอย่าง"""
    _log_setup(window, "\n[Install] เริ่มติดตั้ง dependencies ทั้งหมด...")
    window._btn_install.config(state=tk.DISABLED)
    window.root.update()
    
    try:
        # Install Python packages
        _log_setup(window, "[Install] กำลังติดตั้ง Python packages...")
        
        # Use shell=True on Windows to handle paths/encoding better sometimes, 
        # but here we just need to ensure we capture output correctly
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "playwright", "browser-cookie3", "Pillow", "--user"],
            capture_output=True, text=True, errors='backslashreplace'
        )
        if result.returncode == 0:
            _log_setup(window, "[Install] ✅ Python packages ติดตั้งแล้ว")
        else:
            err_msg = result.stderr.strip()
            _log_setup(window, f"[Install] ❌ ติดตั้งไม่สำเร็จ: {err_msg[:200]}")
            _log_setup(window, "[Install] 💡 ลองรัน INSTALL.bat แทนหากยังไม่ได้")
        
        # Install browser
        _install_browser(window, standalone=False)
        
        _log_setup(window, "[Install] ✅ ติดตั้งเสร็จสมบูรณ์!")
        
    except Exception as e:
        _log_setup(window, f"[Install] ❌ Error: {str(e)}")
    
    window._btn_install.config(state=tk.NORMAL)
    _refresh_status(window)


def _install_browser(window, standalone=True):
    """ติดตั้ง Chromium browser"""
    _log_setup(window, "[Install] กำลังติดตั้ง Chromium browser... (รอสักครู่)")
    if standalone:
        window._btn_install_browser.config(state=tk.DISABLED)
    window.root.update()
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, errors='backslashreplace'
        )
        if result.returncode == 0:
            # Create marker
            marker = PROJECT_ROOT / ".browsers_installed"
            marker.touch()
            _log_setup(window, "[Install] ✅ Chromium ติดตั้งแล้ว")
        else:
            _log_setup(window, f"[Install] ❌ Error: {result.stderr[:200]}")
    except Exception as e:
        _log_setup(window, f"[Install] ❌ Error: {str(e)}")
    
    if standalone:
        window._btn_install_browser.config(state=tk.NORMAL)
        _refresh_status(window)
