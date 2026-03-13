# -*- coding: utf-8 -*-
"""
UI หลัก — ฟอร์มตั้งค่าและปุ่มรัน แยกจาก Logic (รันผ่าน subprocess).
Refactored: แยก Styles, Settings, Process Utils, Tab Builders และ Browser Setup ออกจากไฟล์หลัก
"""

import json
import os
import queue
import re
import shlex
import subprocess
import sys
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# โปรเจกต์ root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ไฟล์เก็บการตั้งค่า UI
UI_SETTINGS_FILE = PROJECT_ROOT / "ui_settings.json"

from activities import list_activities
from core.config import ACTIVITY_ID_DEFAULT, VERSION
from utils.accounts import load_accounts
from utils.console import load_progress

# Import Refactored Modules
from ui.styles import setup_thai_font, apply_dark_theme, BG_ENTRY, BG_MAIN, BG_CARD, FG_MAIN, FG_SUCCESS, FG_ERROR, FG_ACCENT, FG_DIM
from ui.settings_manager import SettingsManager
from ui.process_utils import run_in_thread, build_argv
from ui.tab_builders import (
    build_tab_main, build_tab_daily, build_tab_options,
    build_tab_preview, poll_preview, HAS_PIL
)
from ui.browser_setup import scan_chrome_profiles, kill_chrome, setup_browser
from ui.setup_tab import build_tab_setup


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"EXE Portal Login Automation v{VERSION}")
        self.root.minsize(520, 560)
        self.root.geometry("640x620")

        # Set Icon
        try:
            icon_path = PROJECT_ROOT / "ui" / "icon" / "ge.png"
            if icon_path.exists():
                icon = tk.PhotoImage(file=str(icon_path))
                self.root.iconphoto(False, icon)
        except Exception:
            pass

        self._ui_font = setup_thai_font(self.root)
        apply_dark_theme(self.root)

        self.proc = None
        self.log_queue = queue.Queue()

        # Tkinter Variables
        self.var_file = tk.StringVar(value=str(self._detect_account_file()))
        self.var_screenshots = tk.StringVar(value=str(PROJECT_ROOT / "screenshots"))
        self.var_no_screenshots = tk.BooleanVar(value=False)
        self.var_no_agent = tk.BooleanVar(value=False)
        self.var_use_chrome = tk.BooleanVar(value=True) # Legacy, keeping for compatibility if needed elsewhere
        self.var_browser_type = tk.StringVar(value="chrome")
        self.var_cookies_path = tk.StringVar()
        self.var_chrome_user_data = tk.StringVar(value="")
        self.var_chrome_profile_name = tk.StringVar(value="Default")
        self.var_headless = tk.BooleanVar()
        self.var_human_type = tk.BooleanVar()
        self.var_keep_open = tk.BooleanVar()
        self.var_daily_login_url = tk.StringVar()
        self.var_use_default_browser_cookies = tk.BooleanVar(value=False)
        self.var_start_index = tk.IntVar(value=1)
        self.var_stop_index = tk.IntVar(value=0)
        self.var_keep_browser_settings = tk.BooleanVar(value=False)  # Keep user's manual browser config
        self.var_max_retries = tk.IntVar(value=1)  # Auto-retry count (0-3)
        self.var_parallel = tk.IntVar(value=1)  # Parallel workers (1-5)
        self.var_cleanup_days = tk.IntVar(value=7) # Maintenance days
        self.var_auto_close = tk.BooleanVar(value=False)  # ปิดโปรแกรมเมื่อรันเสร็จ
        self.var_proxy_file = tk.StringVar(value="")  # Proxy list file
        self.var_auto_daily = tk.BooleanVar(value=False)  # Auto Daily Scheduler
        self.var_schedule_hour = tk.IntVar(value=0)  # เวลารัน (ชั่วโมง)
        self.var_schedule_minute = tk.IntVar(value=30)  # เวลารัน (นาที)
        self._schedule_after_id = None  # for cancelling scheduled runs
        self.var_discord_webhook = tk.StringVar(value="")  # Discord webhook URL
        self.var_notify_discord = tk.BooleanVar(value=False)  # Enable Discord notification
        self.var_retry_failed = tk.BooleanVar(value=False)  # Retry failed IDs after delay
        self.var_retry_delay_hours = tk.IntVar(value=1)  # Hours to wait before retry
        self.var_retry_rounds = tk.IntVar(value=2)  # Max retry rounds
        self._retry_round = 0  # Current retry round
        self._retry_after_id = None  # for cancelling scheduled retry
 
        # Auto-detect Chrome User Data path
        self._chrome_profile_placeholder = self._detect_chrome_user_data()
        if not self.var_chrome_user_data.get() and self._chrome_profile_placeholder:
            self.var_chrome_user_data.set(self._chrome_profile_placeholder)

        # Activity Data
        activities = list_activities()
        self.activity_ids = [a.id for a in activities]
        self.activity_names = {a.id: a.name for a in activities}

        # Setup Managers
        self.settings = SettingsManager(UI_SETTINGS_FILE, self)
        
        # Build UI & Initial State
        self._build_ui()
        self.settings.load()
        self._update_account_count()
        self._scan_chrome_profiles()
        self._poll_log()
        self._check_interrupted_progress()

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    @staticmethod
    def _detect_chrome_user_data() -> str:
        """Auto-detect Chrome User Data directory."""
        candidates = [
            Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data",  # Windows
            Path.home() / "Library" / "Application Support" / "Google" / "Chrome",   # macOS
            Path.home() / ".config" / "google-chrome",                                # Linux
        ]
        for p in candidates:
            if p.exists() and (p / "Local State").exists():
                return str(p)
        return ""

    def _detect_account_file(self) -> Path:
        """Auto-detect account file: IDGE.txt first, then any .txt with csv-like content."""
        default = PROJECT_ROOT / "IDGE.txt"
        if default.exists():
            return default
        skip = {"requirements.txt", "proxies.txt"}
        for txt in sorted(PROJECT_ROOT.glob("*.txt")):
            if txt.name.lower() in skip:
                continue
            try:
                with open(txt, encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines()[:5] if l.strip() and not l.startswith("#")]
                if lines and all("," in l for l in lines):
                    return txt
            except Exception:
                continue
        return default  # fallback — user will see file-not-found in the UI field

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        header = ttk.Frame(main); header.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header, text="  GE LOGIN SYSTEM", style="Header.TLabel").pack(side=tk.LEFT)
        self.lbl_account_count = ttk.Label(header, text="", style="Total.TLabel"); self.lbl_account_count.pack(side=tk.RIGHT)

        # Account Section
        f_acc = ttk.Frame(main, style="Card.TFrame", padding=10); f_acc.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(f_acc, text="Account File:", width=12).pack(side=tk.LEFT)
        ttk.Entry(f_acc, textvariable=self.var_file).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(f_acc, text="Browse", width=8, command=self._browse_file).pack(side=tk.LEFT)
        self.var_file.trace_add("write", lambda *_: self._update_account_count())

        # === Section 1: Tabs (fixed height, all scrollable) ===
        self.notebook = ttk.Notebook(main, height=300); self.notebook.pack(fill=tk.X, pady=(0, 5))
        self._tab_canvases = []  # for mousewheel routing

        def _add_plain_tab(label, build_fn):
            """Helper: สร้าง tab ธรรมดา (ไม่มี scrollbar)"""
            outer = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(outer, text=label)
            self._tab_canvases.append(None)  # placeholder for index alignment
            build_fn(self, outer)

        def _add_scrollable_tab(label, build_fn):
            """Helper: สร้าง tab ที่ scroll ได้"""
            outer = ttk.Frame(self.notebook)
            self.notebook.add(outer, text=label)
            canvas = tk.Canvas(outer, highlightthickness=0, bg="#121212")
            scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
            inner = ttk.Frame(canvas, padding=10)
            inner.bind("<Configure>", lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")))
            canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            canvas.bind("<Configure>", lambda e, c=canvas: c.itemconfig("inner", width=e.width))
            self._tab_canvases.append(canvas)
            build_fn(self, inner)

        _add_plain_tab("  Activities  ", build_tab_main)
        _add_plain_tab("  Daily Login  ", build_tab_daily)
        _add_scrollable_tab("  Options  ", build_tab_options)
        _add_scrollable_tab("  Preview  ", build_tab_preview)
        _add_scrollable_tab("  Setup  ", build_tab_setup)

        # Global mousewheel → scroll active tab
        def _on_tab_mousewheel(e):
            idx = self.notebook.index(self.notebook.select())
            if idx < len(self._tab_canvases) and self._tab_canvases[idx] is not None:
                self._tab_canvases[idx].yview_scroll(int(-1 * (e.delta / 120)), "units")
        self.root.bind("<MouseWheel>", _on_tab_mousewheel)

        # === Section 2: Buttons (fixed) ===
        actions = ttk.Frame(main); actions.pack(fill=tk.X, pady=(0, 3))
        self.btn_run = ttk.Button(actions, text="▶ START BOT", style="Run.TButton", command=self._on_run, width=15)
        self.btn_run.pack(side=tk.LEFT, padx=(0, 5))
        self.btn_stop = ttk.Button(actions, text="⏹ STOP", command=self._on_stop, state=tk.DISABLED, width=8)
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        self.btn_dry = ttk.Button(actions, text="Dry Run", command=self._on_dry_run, width=10)
        self.btn_dry.pack(side=tk.LEFT, padx=5)
        ttk.Button(actions, text="Kill Chrome", command=self._kill_chrome, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions, text="Clear Log", command=self._clear_log).pack(side=tk.RIGHT)
        ttk.Button(actions, text="Save Log...", command=self._save_log).pack(side=tk.RIGHT, padx=5)
        ttk.Button(actions, text="Save Config", command=lambda: self.settings.save()).pack(side=tk.RIGHT, padx=5)

        actions2 = ttk.Frame(main); actions2.pack(fill=tk.X, pady=(3, 3))
        self.lbl_version = ttk.Label(actions2, text=f"v{VERSION}", font=("Consolas", 8), foreground=FG_DIM)
        self.lbl_version.pack(side=tk.RIGHT, padx=5)
        ttk.Button(actions2, text="🔄 Update", command=self._check_update, width=10).pack(side=tk.RIGHT, padx=2)
        ttk.Button(actions2, text="View Report", command=self._open_latest_report).pack(side=tk.LEFT)
        ttk.Button(actions2, text="Report Folder", command=self._open_report_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions2, text="Screenshot Folder", command=self._open_screenshot_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions2, text="🔧 Setup Browser", command=self._setup_browser).pack(side=tk.LEFT, padx=15)

        # Progress
        prog_zone = ttk.Frame(main); prog_zone.pack(fill=tk.X, pady=(0, 3))
        self.lbl_progress = ttk.Label(prog_zone, text="Status: Ready"); self.lbl_progress.pack(side=tk.LEFT)
        self.progress_var = tk.DoubleVar(); self.progress_bar = ttk.Progressbar(main, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))

        # === Section 3: Log (expandable) ===
        self.log_text = scrolledtext.ScrolledText(main, height=8, wrap=tk.WORD, state=tk.DISABLED, font=self._ui_font, background="#121212", foreground="#cccccc", borderwidth=0)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        for tag, color in [("info", FG_MAIN), ("success", FG_SUCCESS), ("error", FG_ERROR), ("warning", FG_ACCENT), ("accent", "#888888")]:
            self.log_text.tag_config(tag, foreground=color)
        self._progress_total = self._run_total_accounts = self._completed_count = 0; self._user_stopped = False; self._progress_polling = False

    # === Delegating methods to extracted modules ===
    def _scan_chrome_profiles(self):
        scan_chrome_profiles(self)
    
    def _kill_chrome(self):
        kill_chrome(self)
    
    def _setup_browser(self):
        setup_browser(self)
    
    def _poll_preview(self):
        poll_preview(self)

    def _run_dedicated_daily_login(self):
        url = self.var_daily_login_url.get().strip()
        if not url:
            messagebox.showwarning("คำเตือน", "กรุณาระบุ Daily Login URL", parent=self.root); return
        argv = build_argv(self); idx = argv.index("--activity")
        argv[idx+1] = "ge-daily-login"
        if "--overwrite-url" in argv:
            u_idx = argv.index("--overwrite-url"); argv.pop(u_idx); argv.pop(u_idx)
        argv.extend(["--overwrite-url", url])
        self._start_process(argv)

    # --- Event Handlers & Local Logic ---

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="เลือกไฟล์บัญชี (exe_id,password)",
            filetypes=[("Account files", "*.txt *.csv"), ("Text", "*.txt"), ("CSV", "*.csv"), ("All files", "*.*")],
            initialdir=PROJECT_ROOT,
        )
        if path: self.var_file.set(path)

    def _on_browse_cookies(self):
        path = filedialog.askopenfilename(title="เลือกไฟล์ Cookies (JSON)", filetypes=[("JSON", "*.json"), ("All", "*.*")], initialdir=PROJECT_ROOT)
        if path: self.var_cookies_path.set(path)

    def _browse_screenshots(self):
        path = filedialog.askdirectory(title="เลือกโฟลเดอร์เก็บรูป", initialdir=PROJECT_ROOT)
        if path: self.var_screenshots.set(path)

    def _browse_user_data(self):
        initial = self.var_chrome_user_data.get() or self._chrome_profile_placeholder
        if not Path(initial).exists(): initial = str(Path.home())
        path = filedialog.askdirectory(title="เลือกโฟลเดอร์ User Data ของ Chrome", initialdir=initial)
        if path: self.var_chrome_user_data.set(path)

    def _update_account_count(self):
        path = Path(self.var_file.get().strip())
        if not path or not path.exists():
            self.lbl_account_count.config(text="(ไฟล์ไม่พบ)" if path else ""); return
        try:
            accounts = load_accounts(path)
            self.lbl_account_count.config(text=f"{len(accounts)} บัญชีในไฟล์")
        except OSError: self.lbl_account_count.config(text="(อ่านไม่ได้)")

    def _clear_log(self):
        self.log_text.config(state=tk.NORMAL); self.log_text.delete("1.0", tk.END); self.log_text.config(state=tk.DISABLED)
        self.progress_var.set(0.0); self.lbl_progress.config(text="0/0")

    def _save_log(self):
        path = filedialog.asksaveasfilename(title="บันทึก Log", defaultextension=".txt", filetypes=[("Text", "*.txt")], initialdir=PROJECT_ROOT)
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f: f.write(self.log_text.get("1.0", tk.END))
            messagebox.showinfo("บันทึก Log", f"บันทึกแล้ว: {path}", parent=self.root)
        except OSError as e: messagebox.showerror("ผิดพลาด", f"บันทึกไม่ได้: {e}", parent=self.root)

    def _open_latest_report(self):
        activity_id = self.var_activity.get().strip()
        # ลองเปิด report เฉพาะกิจกรรมก่อน ถ้าไม่มีค่อย fallback ไป root
        activity_path = PROJECT_ROOT / "reports" / activity_id / "latest_report.html"
        root_path = PROJECT_ROOT / "reports" / "latest_report.html"
        if activity_path.exists():
            webbrowser.open(f"file:///{activity_path.absolute()}")
        elif root_path.exists():
            webbrowser.open(f"file:///{root_path.absolute()}")
        else:
            messagebox.showinfo("Report", "ยังไม่มีรายงาน")

    def _open_report_folder(self):
        activity_id = self.var_activity.get().strip()
        # เปิดโฟลเดอร์เฉพาะกิจกรรม ถ้ามี
        activity_dir = PROJECT_ROOT / "reports" / activity_id
        root_dir = PROJECT_ROOT / "reports"
        d = activity_dir if activity_dir.exists() else root_dir
        if d.exists():
            os.startfile(str(d))
        else:
            messagebox.showinfo("Report Folder", f"ยังไม่มีโฟลเดอร์ report\n({d})\n\nรัน Bot สักครั้งเพื่อให้สร้างอัตโนมัติ")

    def _open_screenshot_folder(self):
        custom = self.var_screenshots.get().strip()
        d = Path(custom) if custom else PROJECT_ROOT / "screenshots"
        if d.exists():
            os.startfile(str(d))
        else:
            messagebox.showinfo("Screenshot Folder", f"ยังไม่มีโฟลเดอร์ screenshot\n({d})\n\nรัน Bot สักครั้งเพื่อให้สร้างอัตโนมัติ")

    def _on_run(self): self._start_process(build_argv(self, dry_run=False))
    def _on_dry_run(self): self._start_process(build_argv(self, dry_run=True))

    def _start_process(self, argv):
        self._user_stopped = False
        self._completed_count = 0
        for btn in [self.btn_run, self.btn_dry]:
            btn.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.progress_var.set(0.0); self.lbl_progress.config(text="0/0")
        self._log_append("---\n" + shlex.join(argv) + "\n")

        try:
            acc_path = Path(self.var_file.get().strip())
            self._run_total_accounts = len(load_accounts(acc_path)) if acc_path.exists() else 0
        except: self._run_total_accounts = 0

        def run():
            try:
                self.proc = subprocess.Popen(argv, cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, encoding='utf-8', errors='replace')
                for line in self.proc.stdout: self.log_queue.put(line if line.endswith("\n") else line + "\n")
                self.proc.wait(); self.log_queue.put(None)
            except Exception as e:
                self.log_queue.put(f"Error: {e}\n"); self.log_queue.put(None)
        run_in_thread(run)
        
        # Start progress polling from .progress.json
        self._progress_polling = True
        self.root.after(500, self._poll_progress)

        # Start preview polling
        if HAS_PIL and hasattr(self, '_preview_file'):
            self._preview_last_mtime = 0
            self.root.after(1000, self._poll_preview)

    def _on_stop(self):
        if self.proc and self.proc.poll() is None:
            self._user_stopped = True; self.proc.terminate(); self._log_append("\n[ Stopped by user ]\n")

    def _log_append(self, text):
        self.log_text.config(state=tk.NORMAL)
        success_keys = ["สำเร็จ", "Success", "บันทึกรูป", "บันทึกภาพ", "บันทึกหลักฐาน"]
        error_keys = ["Error", "ผิดพลาด", "Timeout", "ล้มเหลว", "ขัดข้อง", "❌"]
        warning_keys = ["⚠️", "Warning", "ไม่พบ", "พยายาม"]

        tag = "success" if any(k in text for k in success_keys) else \
              "error" if any(k in text for k in error_keys) else \
              "warning" if any(k in text for k in warning_keys) else \
              "accent" if "[" in text else None
        
        self.log_text.insert(tk.END, text, tag); self.log_text.see(tk.END); self.log_text.config(state=tk.DISABLED)

    def _poll_log(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                if line is None: self.root.after(0, self._process_finished); break
                self.root.after(0, lambda s=line: self._log_append(s))
        except queue.Empty: pass
        self.root.after(200, self._poll_log)

    def _poll_progress(self):
        """อ่าน .progress.json ทุก 500ms — source of truth สำหรับ progress bar"""
        if not self._progress_polling:
            return
        prog = load_progress()
        if prog:
            total = prog.get("total", 0)
            completed = prog.get("completed", 0)
            if total > 0:
                self._progress_total = total
                self._completed_count = completed
                self.progress_var.set(100.0 * completed / total)
                self.lbl_progress.config(text=f"{completed}/{total}")
        self.root.after(500, self._poll_progress)

    def _process_finished(self):
        self.proc = None
        self._progress_polling = False
        # อ่านครั้งสุดท้ายจาก .progress.json เพื่อให้ตัวเลขตรง
        prog = load_progress()
        if prog:
            total = prog.get("total", self._progress_total)
            completed = prog.get("completed", self._completed_count)
            if total > 0:
                self._progress_total = total
                self._completed_count = completed
        if self._progress_total > 0: self.progress_var.set(100.0); self.lbl_progress.config(text=f"{self._completed_count}/{self._progress_total}")
        for btn in [self.btn_run, self.btn_dry]: btn.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        # Send notification
        if not self._user_stopped and self.var_notify_discord.get():
            self._send_discord_notification()

        # Auto Retry Failed: check if there are failed IDs to retry
        if not self._user_stopped and self.var_retry_failed.get():
            if self._schedule_retry_failed():
                return  # waiting for retry, don't show finished dialog yet

        if not self._user_stopped:
            try: self.root.bell()
            except: pass
            # Reset retry round counter after final completion
            self._retry_round = 0
            if self.var_auto_daily.get():
                # Auto Daily: schedule next run
                self._schedule_next_run()
            elif self.var_auto_close.get():
                self.lbl_progress.config(text=f"เสร็จแล้ว — กำลังปิดโปรแกรม...")
                self.root.after(1500, self._on_closing)
            else:
                messagebox.showinfo("รันเสร็จสิ้น", f"รันเสร็จสิ้นแล้ว ({self._run_total_accounts or self._progress_total} บัญชี)")

    def _schedule_next_run(self):
        """Calculate next run time and schedule it."""
        from datetime import datetime, timedelta

        now = datetime.now()
        target_h = self.var_schedule_hour.get()
        target_m = self.var_schedule_minute.get()

        # Next run = tomorrow at target time (or today if not yet passed)
        next_run = now.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)

        wait_seconds = (next_run - now).total_seconds()
        wait_ms = int(wait_seconds * 1000)

        next_str = next_run.strftime("%d/%m/%Y %H:%M")
        self._log_append(f"\n[Auto Daily] รันเสร็จแล้ว — รอบถัดไป: {next_str} (อีก {wait_seconds/3600:.1f} ชม.)\n")
        self.lbl_progress.config(text=f"Auto Daily — รอบถัดไป: {next_str}")

        if hasattr(self, '_lbl_next_run'):
            self._lbl_next_run.config(text=f"รอบถัดไป: {next_str} (อีก {wait_seconds/3600:.1f} ชม.)")

        # Cancel previous schedule if any
        if self._schedule_after_id:
            self.root.after_cancel(self._schedule_after_id)

        # Schedule the run
        self._schedule_after_id = self.root.after(wait_ms, self._auto_daily_run)

        # Start countdown display
        self._countdown_target = next_run
        self._update_countdown()

    def _update_countdown(self):
        """Update countdown display every 30 seconds."""
        from datetime import datetime
        if not self.var_auto_daily.get() or self.proc is not None:
            return
        if hasattr(self, '_countdown_target'):
            remaining = (self._countdown_target - datetime.now()).total_seconds()
            if remaining > 0:
                hours = int(remaining // 3600)
                mins = int((remaining % 3600) // 60)
                time_str = self._countdown_target.strftime("%H:%M")
                text = f"Auto Daily — รอบถัดไป {time_str} (อีก {hours}ชม. {mins}นาที)"
                self.lbl_progress.config(text=text)
                if hasattr(self, '_lbl_next_run'):
                    self._lbl_next_run.config(text=text)
                self.root.after(30000, self._update_countdown)

    def _schedule_retry_failed(self) -> bool:
        """Check for failed IDs and schedule a retry run. Returns True if retry scheduled."""
        prog = load_progress()
        if not prog:
            return False

        results = prog.get("results", [])
        # Only retry IDs that failed for NON-credential reasons
        failed_ids = [r["id"] for r in results if not r.get("status") and not r.get("bad_credentials")]
        bad_cred_ids = [r["id"] for r in results if r.get("bad_credentials")]

        if bad_cred_ids:
            self._log_append(f"[Retry] ข้าม {len(bad_cred_ids)} ID รหัสผิด: {', '.join(bad_cred_ids[:5])}")
            if len(bad_cred_ids) > 5:
                self._log_append(f" ...and {len(bad_cred_ids) - 5} more")
            self._log_append("\n")

        if not failed_ids:
            self._retry_round = 0
            return False

        max_rounds = self.var_retry_rounds.get()
        if self._retry_round >= max_rounds:
            self._log_append(f"[Retry] ครบ {max_rounds} รอบแล้ว ยังเหลือ {len(failed_ids)} ID fail\n")
            self._retry_round = 0
            return False

        delay_hours = self.var_retry_delay_hours.get()
        delay_ms = delay_hours * 3600 * 1000
        self._retry_round += 1

        self._log_append(
            f"\n[Retry] พบ {len(failed_ids)} ID fail — รอ {delay_hours} ชม. แล้ว retry "
            f"(รอบ {self._retry_round}/{max_rounds})\n"
        )
        self.lbl_progress.config(
            text=f"Retry รอบ {self._retry_round}/{max_rounds} — รอ {delay_hours} ชม. ({len(failed_ids)} IDs)"
        )
        if hasattr(self, '_lbl_retry_status'):
            from datetime import datetime, timedelta
            retry_at = datetime.now() + timedelta(hours=delay_hours)
            self._lbl_retry_status.config(
                text=f"Retry รอบ {self._retry_round}/{max_rounds} เวลา {retry_at.strftime('%H:%M')} ({len(failed_ids)} IDs)"
            )

        # Store failed IDs for the retry run
        self._retry_failed_ids = failed_ids

        # Cancel previous retry if any
        if self._retry_after_id:
            self.root.after_cancel(self._retry_after_id)

        self._retry_after_id = self.root.after(delay_ms, self._run_retry_failed)
        return True

    def _run_retry_failed(self):
        """Run only the failed IDs."""
        self._retry_after_id = None
        if not hasattr(self, '_retry_failed_ids') or not self._retry_failed_ids:
            return

        failed_ids = self._retry_failed_ids
        from datetime import datetime
        self._log_append(
            f"\n{'='*50}\n"
            f"[Retry] เริ่ม retry {len(failed_ids)} ID — {datetime.now().strftime('%H:%M:%S')} "
            f"(รอบ {self._retry_round}/{self.var_retry_rounds.get()})\n"
            f"{'='*50}\n"
        )

        # Write a temp account file with only failed IDs
        from utils.accounts import load_accounts
        acc_path = Path(self.var_file.get().strip())
        if not acc_path.exists():
            self._log_append("[Retry] ไม่พบไฟล์บัญชี — ยกเลิก retry\n")
            return

        all_accounts = load_accounts(acc_path)
        failed_set = set(failed_ids)
        retry_accounts = [(uid, pw) for uid, pw in all_accounts if uid in failed_set]

        if not retry_accounts:
            self._log_append("[Retry] ไม่พบบัญชีที่ต้อง retry — ข้าม\n")
            return

        # Write temp file
        retry_file = PROJECT_ROOT / ".retry_accounts.txt"
        with open(retry_file, "w", encoding="utf-8") as f:
            for uid, pw in retry_accounts:
                f.write(f"{uid},{pw}\n")

        # Build argv with retry file
        argv = build_argv(self, dry_run=False)
        # Replace --file with retry file
        if "--file" in argv:
            idx = argv.index("--file")
            argv[idx + 1] = str(retry_file)
        # Reset start/stop index
        if "--start-index" in argv:
            idx = argv.index("--start-index")
            argv[idx + 1] = "1"
        if "--stop-index" in argv:
            idx = argv.index("--stop-index")
            argv[idx + 1] = "0"

        self._start_process(argv)

    def _send_discord_notification(self):
        """Send Discord notification after run completes."""
        try:
            from utils.notify import notify_run_complete
            url = self.var_discord_webhook.get().strip()
            if not url:
                return
            prog = load_progress()
            total = prog.get("total", 0) if prog else self._progress_total
            results = prog.get("results", []) if prog else []
            success = sum(1 for r in results if r.get("status")) if results else self._completed_count
            fail = total - success
            activity = self.var_activity.get() if hasattr(self, 'var_activity') else "unknown"

            # Calculate duration from progress
            duration = "N/A"
            if prog and prog.get("timestamp"):
                from datetime import datetime
                try:
                    start = datetime.strptime(prog["timestamp"], "%Y-%m-%d %H:%M:%S")
                    mins = int((datetime.now() - start).total_seconds() / 60)
                    duration = f"{mins}m"
                except Exception:
                    pass

            failed_ids = [r["id"] for r in results if not r.get("status") and not r.get("bad_credentials")] if results else []
            bad_cred_ids = [r["id"] for r in results if r.get("bad_credentials")] if results else []
            ok = notify_run_complete(url, activity, total, success, fail, duration, failed_ids, bad_cred_ids)
            if ok:
                self._log_append("[Discord] Notification sent\n")
            else:
                self._log_append("[Discord] Failed to send notification\n")
        except Exception as e:
            self._log_append(f"[Discord] Error: {e}\n")

    def _reset_schedule(self):
        """Reset timer — apply new time immediately."""
        if self._schedule_after_id:
            self.root.after_cancel(self._schedule_after_id)
            self._schedule_after_id = None
        if self.var_auto_daily.get() and self.proc is None:
            self._schedule_next_run()
            self._log_append("[Auto Daily] Timer reset — ตั้งเวลาใหม่แล้ว\n")
        else:
            if hasattr(self, '_lbl_next_run'):
                self._lbl_next_run.config(text="")
            self.lbl_progress.config(text="Status: Ready")

    def _auto_daily_run(self):
        """Triggered by scheduler — start bot automatically."""
        self._schedule_after_id = None
        if not self.var_auto_daily.get():
            return
        from datetime import datetime
        self._log_append(f"\n{'='*50}\n")
        self._log_append(f"[Auto Daily] เริ่มรันอัตโนมัติ — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        self._log_append(f"{'='*50}\n")
        # Reset start index to 1 for fresh daily run
        self.var_start_index.set(1)
        self._on_run()

    def _check_interrupted_progress(self):
        """ตรวจ .progress.json — ถ้าค้างอยู่ (status=running) ให้ถามว่าจะ resume หรือไม่"""
        prog = load_progress()
        if not prog or prog.get("status") != "running":
            return
        total = prog.get("total", "?")
        completed = prog.get("completed", 0)
        activity = prog.get("activity", "?")
        ts = prog.get("timestamp", "?")
        results = prog.get("results", [])

        # หา index สุดท้ายจาก results array
        if results:
            last_result = max(results, key=lambda r: r.get("index", 0))
            last_id = last_result.get("id", "?")
            last_idx = last_result.get("index", 0)
        else:
            last_id = "?"
            last_idx = 0

        resume_at = last_idx + 1

        msg = (
            f"พบว่ารันค้างอยู่!\n\n"
            f"เสร็จแล้ว: {completed}/{total} บัญชี\n"
            f"ไอดีสุดท้าย: {last_id}\n"
            f"กิจกรรม: {activity}\n"
            f"เวลา: {ts}\n\n"
            f"ต้องการเริ่มต่อจากลำดับที่ {resume_at} หรือไม่?"
        )
        if messagebox.askyesno("Resume — รันค้างอยู่", msg, parent=self.root):
            self.var_start_index.set(resume_at)

    def _check_update(self):
        """Check for updates via git pull from GitHub."""
        REPO_URL = "https://github.com/xToriMicz/GE-Login-Season.git"
        BRANCH = "main"

        # Check if git is available
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True, cwd=PROJECT_ROOT)
        except (FileNotFoundError, subprocess.CalledProcessError):
            messagebox.showerror("Git not found", "ต้องติดตั้ง Git ก่อน\nDownload: https://git-scm.com/downloads", parent=self.root)
            return

        # If no .git folder (downloaded as ZIP), init git repo and connect to remote
        if not (PROJECT_ROOT / ".git").exists():
            self._log_append("[Update] ตั้งค่า Git ครั้งแรก (สำหรับผู้ที่โหลด ZIP)...\n")
            self.root.update()
            subprocess.run(["git", "init", "-b", BRANCH], capture_output=True, cwd=PROJECT_ROOT)
            subprocess.run(["git", "remote", "add", "origin", REPO_URL], capture_output=True, cwd=PROJECT_ROOT)
            fetch_result = subprocess.run(["git", "fetch", "origin"], capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=30)
            if fetch_result.returncode != 0:
                self._log_append(f"[Update] Fetch failed: {fetch_result.stderr.strip()}\n")
                messagebox.showerror("Update", "ไม่สามารถเชื่อมต่อ GitHub ได้\nตรวจสอบอินเทอร์เน็ต", parent=self.root)
                return
            # Reset to match remote — ไม่กระทบไฟล์ user (account .txt, cookies ถูก gitignore)
            subprocess.run(["git", "reset", "--mixed", f"origin/{BRANCH}"], capture_output=True, cwd=PROJECT_ROOT)
            self._log_append("[Update] Git ตั้งค่าเรียบร้อย!\n")
        else:
            # Ensure remote URL is correct (อาจ clone มาจาก repo เก่า)
            current_url = subprocess.run(
                ["git", "remote", "get-url", "origin"], capture_output=True, text=True, cwd=PROJECT_ROOT
            ).stdout.strip()
            if current_url and current_url != REPO_URL:
                subprocess.run(["git", "remote", "set-url", "origin", REPO_URL], capture_output=True, cwd=PROJECT_ROOT)
                self._log_append(f"[Update] เปลี่ยน remote URL เป็น {REPO_URL}\n")

        # Check for remote changes
        self._log_append("[Update] กำลังตรวจสอบอัปเดต...\n")
        self.root.update()

        try:
            # Fetch latest
            fetch = subprocess.run(["git", "fetch", "origin"], capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=30)
            if fetch.returncode != 0:
                self._log_append(f"[Update] Fetch error: {fetch.stderr.strip()}\n")
                messagebox.showerror("Update", "ไม่สามารถตรวจสอบอัปเดตได้\nตรวจสอบอินเทอร์เน็ต", parent=self.root)
                return

            # Compare local vs remote
            local = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=PROJECT_ROOT).stdout.strip()
            remote = subprocess.run(["git", "rev-parse", f"origin/{BRANCH}"], capture_output=True, text=True, cwd=PROJECT_ROOT).stdout.strip()

            if not remote:
                self._log_append("[Update] ไม่พบ remote branch\n")
                messagebox.showerror("Update", f"ไม่พบ branch '{BRANCH}' บน remote", parent=self.root)
                return

            if local == remote:
                self.lbl_version.config(text=f"v{VERSION} (latest)")
                self._log_append("[Update] ใช้เวอร์ชันล่าสุดอยู่แล้ว\n")
                messagebox.showinfo("Update", f"v{VERSION} — ใช้เวอร์ชันล่าสุดอยู่แล้ว", parent=self.root)
                return

            # Show what's new
            log = subprocess.run(
                ["git", "log", "--oneline", f"{local}..{remote}"],
                capture_output=True, text=True, cwd=PROJECT_ROOT
            ).stdout.strip()

            if not messagebox.askyesno(
                "Update Available",
                f"มีอัปเดตใหม่!\n\n{log}\n\nต้องการอัปเดตหรือไม่?\n(โปรแกรมจะ restart หลังอัปเดต)",
                parent=self.root,
            ):
                return

            # Stash local changes to tracked files only (ไม่กระทบ untracked user files)
            subprocess.run(["git", "stash"], capture_output=True, cwd=PROJECT_ROOT)

            # Pull — ใช้ rebase เพื่อลด merge conflict
            result = subprocess.run(
                ["git", "pull", "--rebase", "origin", BRANCH],
                capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=60,
            )

            # Restore local changes
            stash_pop = subprocess.run(["git", "stash", "pop"], capture_output=True, text=True, cwd=PROJECT_ROOT)
            if stash_pop.returncode != 0 and "No stash" not in (stash_pop.stderr or ""):
                self._log_append(f"[Update] Stash conflict (ไฟล์ user ไม่หาย): {stash_pop.stderr.strip()[:100]}\n")

            self._log_append(f"[Update] {result.stdout.strip()}\n")

            if result.returncode == 0:
                self._log_append("[Update] อัปเดตสำเร็จ! กำลัง restart...\n")
                messagebox.showinfo("Update", "อัปเดตสำเร็จ! โปรแกรมจะ restart", parent=self.root)
                # Restart: save settings, launch new process, exit current
                self.settings.save(silent=True)
                subprocess.Popen([sys.executable, "-m", "ui"], cwd=PROJECT_ROOT)
                self.root.destroy()
            else:
                # Abort rebase if stuck
                subprocess.run(["git", "rebase", "--abort"], capture_output=True, cwd=PROJECT_ROOT)
                self._log_append(f"[Update] Error: {result.stderr.strip()}\n")
                messagebox.showerror("Update Failed", f"อัปเดตไม่สำเร็จ:\n{result.stderr[:200]}", parent=self.root)

        except subprocess.TimeoutExpired:
            self._log_append("[Update] Timeout — ตรวจสอบอินเทอร์เน็ต\n")
            messagebox.showerror("Update", "Timeout — ตรวจสอบการเชื่อมต่ออินเทอร์เน็ต", parent=self.root)
        except Exception as e:
            self._log_append(f"[Update] Error: {e}\n")
            messagebox.showerror("Update", f"Error: {e}", parent=self.root)

    def _on_closing(self):
        self.settings.save(silent=True); self.root.destroy()

    def run(self): self.root.mainloop()


def main():
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
