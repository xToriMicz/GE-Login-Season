# -*- coding: utf-8 -*-
"""
Browser Setup utilities — แยกออกมาเพื่อลดขนาด main_window.py
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from tkinter import messagebox

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def scan_chrome_profiles(window):
    """สแกน Chrome Profiles จาก User Data Directory"""
    udata_path = window.var_chrome_user_data.get().strip()
    if not udata_path or not Path(udata_path).exists():
        window.chrome_profile_choices = ["Default"]
        window.cb_profiles.config(values=window.chrome_profile_choices)
        return

    base = Path(udata_path)
    profiles = []
    for pdir in [d for d in base.iterdir() if d.is_dir() and (d.name == "Default" or d.name.startswith("Profile"))]:
        display_name = pdir.name
        pref_file = pdir / "Preferences"
        if pref_file.exists():
            try:
                with open(pref_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    nickname = config.get("profile", {}).get("name")
                    if nickname:
                        display_name = f"{pdir.name} ({nickname})"
            except:
                pass
        profiles.append(display_name)
    
    window.chrome_profile_choices = sorted(
        profiles or ["Default"], 
        key=lambda s: [int(t) if t.isdigit() else t.lower() for t in re.split('([0-9]+)', s)]
    )
    window.cb_profiles.config(values=window.chrome_profile_choices)
    if not any(window.var_chrome_profile_name.get() in p for p in window.chrome_profile_choices):
        window.var_chrome_profile_name.set(window.chrome_profile_choices[0])


def kill_chrome(window):
    """ส่งคำสั่ง Kill Chrome ทั้งหมด"""
    if messagebox.askyesno(
        "ยืนยัน",
        "ระบบจะทำการปิด Chrome ทั้งหมดในเครื่อง (เพื่อแก้ปัญหาเปิด Bot ไม่ขึ้น)\n\nต้องการดำเนินการหรือไม่?",
        parent=window.root
    ):
        try:
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
            messagebox.showinfo("สำเร็จ", "ส่งคำสั่งปิด Chrome เรียบร้อยแล้ว", parent=window.root)
            window._log_append("[System] Sent taskkill to Chrome processes.\n")
        except Exception as e:
            messagebox.showerror("ผิดพลาด", f"ไม่สามารถปิดได้: {e}", parent=window.root)


def setup_browser(window):
    """เปิด Browser ด้วย Sandbox Profile ให้ User ตั้งค่าด้วยตัวเอง"""
    sandbox_dir = PROJECT_ROOT / ".chrome_sandbox"
    source_user_data = window.var_chrome_user_data.get().strip()
    browser_type = window.var_browser_type.get()
    
    # ถ้ายังไม่มี Sandbox หรือ User ไม่ได้เลือก Keep Settings ให้ Clone ใหม่
    if not sandbox_dir.exists():
        if source_user_data and Path(source_user_data).exists():
            prof_val = window.var_chrome_profile_name.get()
            prof_folder = prof_val.split(" (")[0] if " (" in prof_val else prof_val
            source_profile = Path(source_user_data) / prof_folder
            
            if source_profile.exists():
                window._log_append(f"[Setup] กำลัง Clone Profile จาก {source_profile.name}...\n")
                try:
                    sandbox_dir.mkdir(parents=True, exist_ok=True)
                    essential = {"Preferences", "Secure Preferences", "Cookies", "Login Data", "Extensions", "Local Storage"}
                    for item in source_profile.iterdir():
                        if item.name in essential:
                            dst = sandbox_dir / item.name
                            if item.is_dir():
                                shutil.copytree(item, dst, dirs_exist_ok=True)
                            else:
                                shutil.copy2(item, dst)
                    window._log_append(f"[Setup] Clone เรียบร้อย!\n")
                except Exception as e:
                    window._log_append(f"[Setup] ⚠️ Clone error: {e}\n")
            else:
                sandbox_dir.mkdir(parents=True, exist_ok=True)
        else:
            sandbox_dir.mkdir(parents=True, exist_ok=True)
    
    # หา Path ของ Browser
    browser_exe = None
    if browser_type == "chrome":
        for path in [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            str(Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe")
        ]:
            if Path(path).exists():
                browser_exe = path
                break
    elif browser_type == "msedge":
        for path in [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            str(Path.home() / "AppData/Local/Microsoft/Edge/Application/msedge.exe")
        ]:
            if Path(path).exists():
                browser_exe = path
                break
    elif browser_type == "chromium":
        messagebox.showinfo(
            "Chromium ไม่รองรับ Setup",
            "Chromium ของ Playwright ไม่สามารถตั้งค่าล่วงหน้าได้\n\n"
            "💡 แนะนำ: เลือก Chrome หรือ Edge แทน\n"
            "เพื่อใช้งานฟีเจอร์ Setup Browser และ Keep Settings",
            parent=window.root
        )
        return

    if not browser_exe:
        messagebox.showerror("ไม่พบ Browser", f"ไม่พบ {browser_type} ในเครื่อง", parent=window.root)
        return

    window._log_append(f"[Setup] เปิด {browser_type} ด้วย Sandbox Profile...\n")
    window._log_append("[Setup] 💡 ตั้งค่า Chrome ตามต้องการ เช่น ปิด Password Manager\n")
    window._log_append("[Setup] 💡 เมื่อตั้งค่าเสร็จ ปิด Browser แล้วติ๊ก 'Keep Browser Settings'\n")
    
    try:
        subprocess.Popen([
            browser_exe,
            f"--user-data-dir={sandbox_dir}",
            "--no-first-run",
            "--disable-default-apps",
            "chrome://settings/passwords"
        ])
        messagebox.showinfo(
            "Setup Browser",
            "Browser จะเปิดขึ้นมาพร้อมหน้าตั้งค่า Password\n\n"
            "📌 ปิด 'Offer to save passwords' และ 'Warn about passwords in data breach'\n\n"
            "เมื่อตั้งค่าเสร็จ:\n"
            "1. ปิด Browser\n"
            "2. ติ๊ก ✓ 'Keep Browser Settings'\n"
            "3. กด START BOT ได้เลย",
            parent=window.root
        )
    except Exception as e:
        messagebox.showerror("ผิดพลาด", f"ไม่สามารถเปิด Browser ได้: {e}", parent=window.root)
