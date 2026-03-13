# -*- coding: utf-8 -*-
"""
Tab builders สำหรับ UI หลัก — แยกออกมาเพื่อลดขนาด main_window.py
"""

import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# Auto-install Pillow if not found
HAS_PIL = False
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    print("[System] Pillow not found, auto-installing...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "-q"])
        from PIL import Image, ImageTk
        HAS_PIL = True
        print("[System] Pillow installed successfully!")
    except Exception as e:
        print(f"[System] Failed to install Pillow: {e}")

from core.config import ACTIVITY_ID_DEFAULT
from ui.styles import BG_ENTRY, BG_CARD, FG_DIM, FG_ERROR, FG_SUCCESS
from utils.console import load_progress
from utils.maintenance import get_junk_stats, clean_previews, clean_logs, clean_old_files

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_tab_main(window, parent):
    """สร้างแท็บ Activities หลัก"""

    # Quick Start hint
    window._lbl_quickstart = ttk.Label(
        parent,
        text="✅ พร้อมใช้งาน — เลือกไฟล์บัญชีแล้วกด START BOT ได้เลย",
        foreground=FG_SUCCESS,
    )
    window._lbl_quickstart.pack(fill=tk.X, pady=(0, 8))

    f1 = ttk.Frame(parent); f1.pack(fill=tk.X, pady=2)
    ttk.Label(f1, text="Activity:", width=12).pack(side=tk.LEFT)
    window.var_activity = tk.StringVar(value=ACTIVITY_ID_DEFAULT)
    ttk.Combobox(f1, textvariable=window.var_activity, values=window.activity_ids, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True)

    ttk.Label(f1, text="  Start at #:", width=10).pack(side=tk.LEFT)
    tk.Spinbox(f1, from_=1, to=9999, textvariable=window.var_start_index, width=5, bg=BG_ENTRY, fg="white", insertbackground="white", borderwidth=0).pack(side=tk.LEFT)

    ttk.Label(f1, text="  Stop at #:", width=9).pack(side=tk.LEFT)
    tk.Spinbox(f1, from_=0, to=9999, textvariable=window.var_stop_index, width=5, bg=BG_ENTRY, fg="white", insertbackground="white", borderwidth=0).pack(side=tk.LEFT)
    ttk.Label(f1, text=" (0 = End)").pack(side=tk.LEFT)

    # --- Advanced Settings (collapsed by default) ---
    adv_frame = ttk.LabelFrame(parent, text=" Advanced (ไม่ต้องตั้งค่าถ้าใช้งานปกติ) ", padding=5)
    adv_frame.pack(fill=tk.X, pady=(8, 2))

    for text, var, cmd in [
        ("Cookies File:", window.var_cookies_path, window._on_browse_cookies),
        ("Chrome Path:", window.var_chrome_user_data, window._browse_user_data)
    ]:
        f = ttk.Frame(adv_frame); f.pack(fill=tk.X, pady=2)
        ttk.Label(f, text=text, width=12).pack(side=tk.LEFT)
        ttk.Entry(f, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(f, text="Browse", width=8, command=cmd).pack(side=tk.LEFT)

    window.var_chrome_user_data.trace_add("write", lambda *_: window._scan_chrome_profiles())

    f_profile_sel = ttk.Frame(adv_frame); f_profile_sel.pack(fill=tk.X, pady=2)
    ttk.Label(f_profile_sel, text="Select Profile:", width=12).pack(side=tk.LEFT)
    window.cb_profiles = ttk.Combobox(f_profile_sel, textvariable=window.var_chrome_profile_name, state="readonly")
    window.cb_profiles.pack(side=tk.LEFT, fill=tk.X, expand=True)
    ttk.Label(f_profile_sel, text="(โปรไฟล์ที่จะใช้ดึง Cookie)").pack(side=tk.LEFT, padx=5)

    f_screenshots = ttk.Frame(adv_frame); f_screenshots.pack(fill=tk.X, pady=2)
    ttk.Label(f_screenshots, text="Screenshot Dir:", width=12).pack(side=tk.LEFT)
    ttk.Entry(f_screenshots, textvariable=window.var_screenshots).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    ttk.Button(f_screenshots, text="Browse", width=8, command=window._browse_screenshots).pack(side=tk.LEFT)


def _update_junk_stats(window):
    """อัปเดตข้อความแสดงขนาดไฟล์ขยะ"""
    try:
        stats = get_junk_stats()
        text = f"📊 ไฟล์ขยะทั้งหมด: {stats['total_size']} MB (Log: {stats['logs_size']} MB, Preview: {stats['preview_size']} MB)"
        window.lbl_junk_stats.config(text=text)
    except Exception as e:
        window.lbl_junk_stats.config(text=f"❌ ตรวจสอบขนาดไฟล์ไม่ได้: {str(e)[:50]}", foreground=FG_ERROR)


def build_tab_options(window, parent):
    """สร้างแท็บ Options — รวมการตั้งค่า Bot ทั้งหมด"""
    parent.configure(style="Card.TFrame")

    # --- Bot Behavior ---
    sec1 = ttk.LabelFrame(parent, text=" Bot Behavior ", padding=10)
    sec1.pack(fill=tk.X, pady=(0, 10))

    row1 = ttk.Frame(sec1); row1.pack(fill=tk.X, pady=2)
    ttk.Checkbutton(row1, text="Headless (ไม่เปิดหน้าต่าง)", variable=window.var_headless).pack(anchor=tk.W)
    row2 = ttk.Frame(sec1); row2.pack(fill=tk.X, pady=2)
    ttk.Checkbutton(row2, text="Human Type (พิมพ์ช้าเหมือนคน)", variable=window.var_human_type).pack(anchor=tk.W)
    row3 = ttk.Frame(sec1); row3.pack(fill=tk.X, pady=2)
    ttk.Checkbutton(row3, text="No Agent (ปิดโหมดหลบ Bot Detection)", variable=window.var_no_agent).pack(anchor=tk.W)
    row4 = ttk.Frame(sec1); row4.pack(fill=tk.X, pady=2)
    ttk.Checkbutton(row4, text="Debug (เปิด Browser ค้างไว้ตอนจบ)", variable=window.var_keep_open).pack(anchor=tk.W)
    row5 = ttk.Frame(sec1); row5.pack(fill=tk.X, pady=2)
    window._cb_auto_close = ttk.Checkbutton(row5, text="Auto Close (ปิดโปรแกรมเมื่อรันเสร็จ)", variable=window.var_auto_close)
    window._cb_auto_close.pack(anchor=tk.W)

    # --- Auto Daily Scheduler ---
    sec_sched = ttk.LabelFrame(parent, text=" Auto Daily (เปิดทิ้งไว้ รันทุกวันอัตโนมัติ) ", padding=10)
    sec_sched.pack(fill=tk.X, pady=(0, 10))

    sched_row1 = ttk.Frame(sec_sched); sched_row1.pack(fill=tk.X, pady=2)
    window._cb_auto_daily = ttk.Checkbutton(sched_row1, text="เปิดใช้งาน Auto Daily", variable=window.var_auto_daily)
    window._cb_auto_daily.pack(side=tk.LEFT)

    # Mutual exclusion: Auto Daily <-> Auto Close
    def _on_auto_daily_toggle(*_):
        if window.var_auto_daily.get():
            window.var_auto_close.set(False)
            window._cb_auto_close.config(state=tk.DISABLED)
        else:
            window._cb_auto_close.config(state=tk.NORMAL)

    def _on_auto_close_toggle(*_):
        if window.var_auto_close.get():
            window.var_auto_daily.set(False)
            window._cb_auto_daily.config(state=tk.DISABLED)
        else:
            window._cb_auto_daily.config(state=tk.NORMAL)

    window.var_auto_daily.trace_add("write", _on_auto_daily_toggle)
    window.var_auto_close.trace_add("write", _on_auto_close_toggle)

    sched_row2 = ttk.Frame(sec_sched); sched_row2.pack(fill=tk.X, pady=2)
    ttk.Label(sched_row2, text="รันทุกวันเวลา:").pack(side=tk.LEFT)
    tk.Spinbox(sched_row2, from_=0, to=23, textvariable=window.var_schedule_hour, width=3,
               format="%02.0f", bg=BG_ENTRY, fg="white", insertbackground="white", borderwidth=0).pack(side=tk.LEFT, padx=2)
    ttk.Label(sched_row2, text=":").pack(side=tk.LEFT)
    tk.Spinbox(sched_row2, from_=0, to=59, textvariable=window.var_schedule_minute, width=3,
               format="%02.0f", bg=BG_ENTRY, fg="white", insertbackground="white", borderwidth=0).pack(side=tk.LEFT, padx=2)
    ttk.Label(sched_row2, text=" น.").pack(side=tk.LEFT)

    sched_row3 = ttk.Frame(sec_sched); sched_row3.pack(fill=tk.X, pady=(5, 0))
    window._lbl_next_run = ttk.Label(sched_row3, text="", foreground=FG_DIM)
    window._lbl_next_run.pack(side=tk.LEFT)
    ttk.Button(sched_row3, text="Reset Timer", width=12, command=window._reset_schedule).pack(side=tk.RIGHT)

    ttk.Label(sec_sched, text="  เปิดโปรแกรมทิ้งไว้ → รันเสร็จ → รอถึงเวลา → รันวันถัดไปอัตโนมัติ",
              foreground=FG_DIM).pack(anchor=tk.W)

    # --- Notifications ---
    sec_notif = ttk.LabelFrame(parent, text=" Notifications ", padding=10)
    sec_notif.pack(fill=tk.X, pady=(0, 10))

    notif_row1 = ttk.Frame(sec_notif); notif_row1.pack(fill=tk.X, pady=2)
    ttk.Checkbutton(notif_row1, text="Discord", variable=window.var_notify_discord).pack(side=tk.LEFT)

    notif_row2 = ttk.Frame(sec_notif); notif_row2.pack(fill=tk.X, pady=2)
    ttk.Label(notif_row2, text="Webhook URL:").pack(side=tk.LEFT)
    ttk.Entry(notif_row2, textvariable=window.var_discord_webhook).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))

    def _test_discord():
        from utils.notify import send_discord
        url = window.var_discord_webhook.get().strip()
        if not url:
            messagebox.showwarning("Discord", "กรุณาใส่ Webhook URL"); return
        ok = send_discord(url, "GE Login Bot — Test", "Notification is working!")
        if ok:
            messagebox.showinfo("Discord", "ส่งสำเร็จ! เช็ค Discord ได้เลย")
        else:
            messagebox.showerror("Discord", "ส่งไม่สำเร็จ — ตรวจสอบ Webhook URL")

    ttk.Button(notif_row2, text="Test", width=6, command=_test_discord).pack(side=tk.LEFT)

    ttk.Label(sec_notif,
              text="  วิธีสร้าง: Discord > Server Settings > Integrations > Webhooks > New Webhook > Copy URL",
              foreground=FG_DIM).pack(anchor=tk.W)

    # --- Auto Retry Failed ---
    sec_retry = ttk.LabelFrame(parent, text=" Auto Retry Failed (รัน ID ที่ fail ซ้ำอีกรอบ) ", padding=10)
    sec_retry.pack(fill=tk.X, pady=(0, 10))

    retry_row1 = ttk.Frame(sec_retry); retry_row1.pack(fill=tk.X, pady=2)
    ttk.Checkbutton(retry_row1, text="เปิดใช้งาน Auto Retry Failed", variable=window.var_retry_failed).pack(side=tk.LEFT)

    retry_row2 = ttk.Frame(sec_retry); retry_row2.pack(fill=tk.X, pady=2)
    ttk.Label(retry_row2, text="รอก่อน retry:").pack(side=tk.LEFT)
    tk.Spinbox(retry_row2, from_=1, to=6, textvariable=window.var_retry_delay_hours, width=3,
               bg=BG_ENTRY, fg="white", insertbackground="white", borderwidth=0).pack(side=tk.LEFT, padx=2)
    ttk.Label(retry_row2, text="ชม.    จำนวนรอบ retry:").pack(side=tk.LEFT)
    tk.Spinbox(retry_row2, from_=1, to=5, textvariable=window.var_retry_rounds, width=3,
               bg=BG_ENTRY, fg="white", insertbackground="white", borderwidth=0).pack(side=tk.LEFT, padx=2)
    ttk.Label(retry_row2, text="รอบ").pack(side=tk.LEFT)

    window._lbl_retry_status = ttk.Label(sec_retry, text="", foreground=FG_DIM)
    window._lbl_retry_status.pack(anchor=tk.W, pady=(5, 0))

    ttk.Label(sec_retry,
              text="  รันจบ → มี fail → รอ N ชม. → รันเฉพาะ ID ที่ fail → ซ้ำได้สูงสุด N รอบ",
              foreground=FG_DIM).pack(anchor=tk.W)

    # --- Browser ---
    sec2 = ttk.LabelFrame(parent, text=" Browser ", padding=10)
    sec2.pack(fill=tk.X, pady=(0, 10))

    brow_row = ttk.Frame(sec2); brow_row.pack(fill=tk.X, pady=2)
    ttk.Label(brow_row, text="Browser:").pack(side=tk.LEFT)
    window.cb_browser = ttk.Combobox(brow_row, textvariable=window.var_browser_type, values=["chrome", "msedge", "chromium"], state="readonly", width=12)
    window.cb_browser.pack(side=tk.LEFT, padx=(5, 15))
    ttk.Checkbutton(brow_row, text="Use Default Browser Cookies", variable=window.var_use_default_browser_cookies).pack(side=tk.LEFT)

    brow_row2 = ttk.Frame(sec2); brow_row2.pack(fill=tk.X, pady=2)
    ttk.Checkbutton(brow_row2, text="Keep Browser Settings (ไม่ reset profile ทุกรอบ)", variable=window.var_keep_browser_settings).pack(anchor=tk.W)

    # --- Performance ---
    sec3 = ttk.LabelFrame(parent, text=" Performance ", padding=10)
    sec3.pack(fill=tk.X, pady=(0, 10))

    perf_row = ttk.Frame(sec3); perf_row.pack(fill=tk.X, pady=2)
    ttk.Label(perf_row, text="Retry (จำนวนครั้งที่ลองใหม่เมื่อ error):").pack(side=tk.LEFT)
    ttk.Spinbox(perf_row, from_=0, to=3, textvariable=window.var_max_retries, width=4, state="readonly").pack(side=tk.LEFT, padx=5)

    perf_row2 = ttk.Frame(sec3); perf_row2.pack(fill=tk.X, pady=2)
    ttk.Label(perf_row2, text="Parallel (จำนวน Browser พร้อมกัน):").pack(side=tk.LEFT)
    ttk.Spinbox(perf_row2, from_=1, to=5, textvariable=window.var_parallel, width=4, state="readonly").pack(side=tk.LEFT, padx=5)

    perf_row3 = ttk.Frame(sec3); perf_row3.pack(fill=tk.X, pady=2)
    ttk.Label(perf_row3, text="Proxy File:").pack(side=tk.LEFT)
    ttk.Entry(perf_row3, textvariable=window.var_proxy_file).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
    def _browse_proxy():
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="เลือกไฟล์ Proxy List", filetypes=[("Text", "*.txt"), ("All", "*.*")], initialdir=PROJECT_ROOT)
        if path: window.var_proxy_file.set(path)
    ttk.Button(perf_row3, text="Browse", width=8, command=_browse_proxy).pack(side=tk.LEFT)
    ttk.Label(sec3, text="  รูปแบบ: host:port หรือ user:pass@host:port (1 proxy/บรรทัด)", foreground=FG_DIM).pack(anchor=tk.W)

    # --- Output ---
    sec4 = ttk.LabelFrame(parent, text=" Output ", padding=10)
    sec4.pack(fill=tk.X, pady=(0, 10))

    ttk.Checkbutton(sec4, text="No Screenshots (ไม่บันทึกภาพหลักฐาน)", variable=window.var_no_screenshots).pack(anchor=tk.W, pady=2)

    # --- Maintenance ---
    sec5 = ttk.LabelFrame(parent, text=" Maintenance (จัดการไฟล์ขยะ) ", padding=10)
    sec5.pack(fill=tk.X, pady=(0, 10))

    stats_row = ttk.Frame(sec5)
    stats_row.pack(fill=tk.X)
    window.lbl_junk_stats = ttk.Label(stats_row, text="กำลังคำนวณขนาดไฟล์ขยะ...")
    window.lbl_junk_stats.pack(side=tk.LEFT)

    btn_row = ttk.Frame(sec5)
    btn_row.pack(fill=tk.X, pady=(10, 0))

    def _do_clean_previews():
        clean_previews()
        _update_junk_stats(window)
        messagebox.showinfo("สำเร็จ", "ล้างรูป Preview เรียบร้อยแล้ว")

    def _do_clean_logs():
        if messagebox.askyesno("ยืนยัน", "ต้องการล้างประวัติ Log ทั้งหมดหรือไม่?"):
            clean_logs()
            _update_junk_stats(window)
            window._clear_log()
            messagebox.showinfo("สำเร็จ", "ล้าง Log เรียบร้อยแล้ว")

    def _do_clean_old():
        days = window.var_cleanup_days.get()
        if days < 0: days = 0
        count = clean_old_files(days=days)
        _update_junk_stats(window)
        messagebox.showinfo("สำเร็จ", f"ลบไฟล์ที่เก่ากว่า {days} วันเรียบร้อยแล้ว ({count} รายการ)")

    ttk.Button(btn_row, text="ล้าง Preview", command=_do_clean_previews).pack(side=tk.LEFT, padx=2)
    ttk.Button(btn_row, text="ลบไฟล์ Log (Disk)", command=_do_clean_logs).pack(side=tk.LEFT, padx=2)
    ttk.Label(btn_row, text="  ลบไฟล์เก่ากว่า:").pack(side=tk.LEFT, padx=(5, 2))
    tk.Spinbox(btn_row, from_=0, to=365, textvariable=window.var_cleanup_days, width=3, bg=BG_ENTRY, fg="white", insertbackground="white", borderwidth=0).pack(side=tk.LEFT)
    ttk.Label(btn_row, text=" วัน").pack(side=tk.LEFT)
    ttk.Button(btn_row, text="ลบไฟล์เก่า", command=_do_clean_old).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_row, text="รีเฟรช", width=8, command=lambda: _update_junk_stats(window)).pack(side=tk.RIGHT)

    parent.after(1000, lambda: _update_junk_stats(window))


def build_tab_daily(window, parent):
    """สร้างแท็บ Daily Login"""
    parent.configure(style="Card.TFrame")
    ttk.Label(parent, text=" 📅 GE Daily Login (กดรับของรายวัน) ", style="Section.TLabel").pack(fill=tk.X, pady=(0, 10))
    
    f_login = ttk.Frame(parent, style="Card.TFrame"); f_login.pack(fill=tk.X, pady=2)
    ttk.Label(f_login, text="Activity URL:", width=15, style="Card.TFrame.TLabel").pack(side=tk.LEFT)
    ttk.Entry(f_login, textvariable=window.var_daily_login_url).pack(side=tk.LEFT, fill=tk.X, expand=True)

    ttk.Label(parent, text="* สลับไปแท็บ Activities แล้วเลือกกิจกรรม Daily Login เพื่อรัน", style="Card.TFrame.TLabel").pack(pady=10)


def build_tab_preview(window, parent):
    """สร้าง Tab สำหรับแสดง Preview ขณะ Bot ทำงาน"""
    if not HAS_PIL:
        ttk.Label(parent, text="❌ ต้องติดตั้ง Pillow ก่อน: pip install Pillow", foreground=FG_ERROR).pack(pady=20)
        return

    ttk.Label(parent, text="📸 หน้าจอขณะ Bot ทำงาน (อัปเดตทุก 3 วินาที)", foreground=FG_DIM).pack(pady=(0, 5))

    # Canvas for preview image
    window.preview_canvas = tk.Canvas(parent, width=640, height=360, bg=BG_CARD, highlightthickness=1, highlightbackground=FG_DIM)
    window.preview_canvas.pack(pady=5)

    # Status info bar ใต้รูป
    status_frame = ttk.Frame(parent)
    status_frame.pack(fill=tk.X, padx=10, pady=(2, 5))
    window._preview_status_lbl = tk.Label(
        status_frame, text="รอเริ่ม Bot...", fg=FG_DIM, bg=BG_CARD,
        font=("Segoe UI", 10), anchor=tk.W, padx=8, pady=4
    )
    window._preview_status_lbl.pack(fill=tk.X)

    # Placeholder text
    window.preview_canvas.create_text(320, 180, text="เริ่ม Bot เพื่อดู Preview", fill=FG_DIM, font=("Segoe UI", 12))

    # Store reference to avoid garbage collection
    window._preview_photo = None
    window._preview_file = PROJECT_ROOT / ".preview" / "current.png"
    window._preview_last_mtime = 0


def poll_preview(window):
    """ตรวจสอบและอัปเดตรูป Preview + สถานะล่าสุด ทุก 2 วินาที"""
    if not HAS_PIL:
        return

    try:
        if hasattr(window, '_preview_file') and window._preview_file.exists():
            mtime = window._preview_file.stat().st_mtime
            if mtime > window._preview_last_mtime:
                window._preview_last_mtime = mtime

                img = Image.open(window._preview_file)
                img.thumbnail((640, 360), Image.Resampling.LANCZOS)

                window._preview_photo = ImageTk.PhotoImage(img)
                window.preview_canvas.delete("all")
                window.preview_canvas.create_image(320, 180, anchor=tk.CENTER, image=window._preview_photo)
    except Exception:
        pass

    # อ่าน progress แสดงสถานะล่าสุด
    try:
        progress = load_progress()
        if progress and hasattr(window, '_preview_status_lbl'):
            results = progress.get("results", [])
            total = progress.get("total", 0)
            completed = len(results)
            activity = progress.get("activity", "")

            if results:
                last = results[-1]
                last_id = last.get("id", "?")
                last_ok = last.get("status", False)
                last_time = last.get("time", "")

                success_count = sum(1 for r in results if r.get("status"))
                fail_count = completed - success_count

                status_icon = "✅" if last_ok else "❌"
                status_word = "OK" if last_ok else "FAIL"

                text = (
                    f"{status_icon} {last_id} → {status_word} ({last_time})  |  "
                    f"Progress: {completed}/{total}  |  "
                    f"✅ {success_count}  ❌ {fail_count}  |  "
                    f"{activity}"
                )
                color = FG_SUCCESS if last_ok else FG_ERROR
                window._preview_status_lbl.config(text=text, fg=color)
            else:
                window._preview_status_lbl.config(
                    text=f"กำลังเริ่ม... ({activity}, {total} accounts)", fg=FG_DIM
                )
    except Exception:
        pass

    if window.proc and window.proc.poll() is None:
        window.root.after(2000, lambda: poll_preview(window))
