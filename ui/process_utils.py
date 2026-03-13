# -*- coding: utf-8 -*-
import subprocess
import threading
import sys
from pathlib import Path

def run_in_thread(target, daemon=True):
    t = threading.Thread(target=target, daemon=daemon)
    t.start()
    return t

def build_argv(window, dry_run=False):
    """สร้างรายการ argument สำหรับรัน login.py"""
    argv = [
        sys.executable, "-m", "login",
        "--file", window.var_file.get().strip(),
        "--activity", window.var_activity.get().strip(),
    ]
    
    if not window.var_no_screenshots.get():
        argv.extend(["--screenshots-dir", window.var_screenshots.get().strip()])
    else:
        argv.append("--no-screenshots")
        
    if window.var_headless.get():
        argv.append("--headless")
        
    if window.var_no_agent.get():
        argv.append("--no-agent")
        
    if window.var_cookies_path.get().strip():
        argv.extend(["--cookies", window.var_cookies_path.get().strip()])

    if window.var_browser_type.get():
        argv.extend(["--browser", window.var_browser_type.get()])
    
    if hasattr(window, "var_use_default_browser_cookies") and window.var_use_default_browser_cookies.get():
        argv.append("--use-default-browser-cookies")
        
    if hasattr(window, "var_chrome_user_data") and window.var_chrome_user_data.get().strip():
        ud_path = window.var_chrome_user_data.get().strip()
        prof_val = window.var_chrome_profile_name.get()
        # ตัดส่วน (Nickname) ออก โดยหาจากเครื่องหมาย " ("
        prof_folder = prof_val.split(" (")[0] if " (" in prof_val else prof_val
        full_path = str(Path(ud_path) / prof_folder)
        argv.extend(["--chrome-user-data", full_path])

    # ถ้า User ติ๊ก Keep Browser Settings ให้ส่ง flag ไปด้วย
    if hasattr(window, "var_keep_browser_settings") and window.var_keep_browser_settings.get():
        argv.append("--keep-browser-settings")

    if window.var_human_type.get():
        argv.append("--human-type")
        
    if window.var_keep_open.get():
        argv.append("--keep-open")
        
    if hasattr(window, "var_start_index") and window.var_start_index.get() > 1:
        argv.extend(["--start-index", str(window.var_start_index.get())])

    if hasattr(window, "var_stop_index") and window.var_stop_index.get() > 0:
        argv.extend(["--stop-index", str(window.var_stop_index.get())])


    # Max Retries
    if hasattr(window, "var_max_retries"):
        retry_val = window.var_max_retries.get()
        if retry_val != 1:  # Only pass if not default
            argv.extend(["--max-retries", str(retry_val)])

    # Parallel workers
    if hasattr(window, "var_parallel"):
        parallel_val = window.var_parallel.get()
        if parallel_val > 1:
            argv.extend(["--parallel", str(parallel_val)])

    # Proxy file
    if hasattr(window, "var_proxy_file") and window.var_proxy_file.get().strip():
        argv.extend(["--proxy-file", window.var_proxy_file.get().strip()])

    # Always enable preview mode for UI (parallel mode ignores this internally)
    argv.append("--preview-mode")

    if dry_run:
        argv.append("--dry-run")
        
    return argv
