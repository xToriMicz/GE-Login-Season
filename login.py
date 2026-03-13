#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXE Portal Login Automation — Entry point (CLI).
Single Responsibility: อ่านอาร์กิวเมนต์, โหลดกิจกรรม/บัญชี, วนเรียก flow และแสดงสถานะ
Logic อยู่ใน core/ และ utils/ ตามกฎ Single Responsibility
"""

import argparse
import sys
import io
import json
import random
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue

# ปรับแก้ปัญหา encoding บน Windows (charmap error)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

from activities import get_activity, list_activities
from core.config import ACTIVITY_ID_DEFAULT, LOGIN_URL_DEFAULT, LOGIN_URL_LEGACY
from core.login_flow import run_login_flow
from utils.accounts import load_accounts
from utils.agent import USER_AGENT, hide_automation
from utils.browser_cookies import get_chrome_cookies_for_playwright
from utils.console import status, save_progress, init_progress, clear_progress
from utils.reporter import generate_reports
from utils.run_history import save_run_history
from core.retry import should_retry, get_retry_delay
from utils.preview import save_preview, clear_preview

# โฟลเดอร์โปรเจกต์ (ใช้ตอน --use-chrome สำหรับ persistent profile)
PROJECT_ROOT = Path(__file__).resolve().parent

def _clone_profile(source_dir: Path, target_dir: Path):
    """Clone Chrome profile without locking issues (Modern approach for 2024-2025)"""
    import shutil
    import os
    
    if target_dir.exists():
        try: shutil.rmtree(target_dir, ignore_errors=True)
        except: pass
    
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # ไฟล์/โฟลเดอร์สำคัญที่ต้องเอาไปเพื่อให้ Login ไม่หลุด, Cloudflare เชื่อใจ, และ Settings ครบ
    # ใช้ชื่อตรงๆ (exact match) เพื่อให้แน่ใจว่า copy ถูกตัว
    essential_items = {
        # Core Data
        "Cookies", "Cookies-journal",
        "Network", 
        "Local Storage", "Session Storage", 
        "Login Data", "Login Data-journal",
        "Web Data", "Web Data-journal",
        "History", "History-journal",
        
        # Preferences & Settings (สำคัญมาก!)
        "Preferences",           # ไฟล์หลักเก็บการตั้งค่าทั้งหมด
        "Secure Preferences",    # การตั้งค่าที่ต้องการ security
        "Local State",           # การตั้งค่าระดับ browser (นอก profile)
        
        # Extensions
        "Extensions",
        "Extension State", 
        "Extension Rules",
        "Extension Scripts",
        "Local Extension Settings",
        "Managed Extension Settings",
        "Extension Cookies",
        
        # Security & Cloudflare
        "Trust Tokens",
        "Origin Bound Certs",
        
        # Sync & Storage
        "Sync Data",
        "IndexedDB",
        "databases",
        "Cache",
        "Code Cache",
        "GPUCache",
        
        # Additional important data
        "Bookmarks",
        "Favicons",
        "Top Sites",
        "Visited Links",
        "TransportSecurity",
        "DIPS",
    }
    
    print(f"[System] Cloning profile from {source_dir.name} to sandbox...", flush=True)
    
    copied_count = 0
    failed_items = []
    
    for item in os.listdir(source_dir):
        # ใช้ exact match แทน substring match
        if item in essential_items:
            src = source_dir / item
            dst = target_dir / item
            try:
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns('*.lock', 'SingletonLock', 'lockfile', 'LOCK'))
                else:
                    shutil.copy2(src, dst)
                copied_count += 1
            except Exception as e:
                failed_items.append(f"{item}: {str(e)[:30]}")
    
    print(f"[System] Sandbox ready! Copied {copied_count} items.", flush=True)
    if failed_items:
        print(f"[System] ⚠️ Could not copy: {', '.join(failed_items[:5])}", flush=True)


def _kill_chrome_processes():
    """บังคับปิด Chrome ทั้งหมดเพื่อป้องกัน session ซ้อนทับ"""
    import subprocess
    import os
    try:
        if os.name == 'nt':
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["taskkill", "/F", "/IM", "googleupdate.exe", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass


def _load_proxies(proxy_file: Path) -> list[dict]:
    """
    โหลดรายการ proxy จากไฟล์
    รูปแบบรองรับ:
      host:port
      user:pass@host:port
      socks5://host:port
      socks5://user:pass@host:port
      http://host:port
    คืน list of Playwright proxy dicts: {"server": ..., "username": ..., "password": ...}
    """
    if not proxy_file or not proxy_file.exists():
        return []
    proxies = []
    with open(proxy_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            proxy = _parse_proxy(line)
            if proxy:
                proxies.append(proxy)
    return proxies


def _parse_proxy(raw: str) -> dict:
    """Parse proxy string เป็น Playwright proxy dict"""
    # ถ้าไม่มี scheme ให้ใส่ http://
    if "://" not in raw:
        raw = "http://" + raw

    scheme = raw.split("://")[0]  # http, socks5, etc.
    rest = raw.split("://", 1)[1]

    username = password = None
    if "@" in rest:
        auth, hostport = rest.rsplit("@", 1)
        if ":" in auth:
            username, password = auth.split(":", 1)
        else:
            username = auth
    else:
        hostport = rest

    server = f"{scheme}://{hostport}"
    proxy = {"server": server}
    if username:
        proxy["username"] = username
    if password:
        proxy["password"] = password
    return proxy


class _RateLimiter:
    """Global rate limiter — ให้ทุก worker รวมกันยิงได้ไม่เกิน 1 request ต่อ min_interval วินาที"""
    def __init__(self, min_interval: float = 4.0):
        self._lock = threading.Lock()
        self._last_request = 0.0
        self._min_interval = min_interval
        self._backoff_until = 0.0  # ถ้าโดน block จะตั้ง backoff ยาว

    def wait(self, worker_tag: str = ""):
        """รอจนกว่าจะถึงคิว — thread-safe"""
        with self._lock:
            now = time.time()
            # ถ้าอยู่ใน backoff (โดน block) รอยาว
            if now < self._backoff_until:
                wait_time = self._backoff_until - now
                status(0, 0, f"[{worker_tag}] IP cooldown — รอ {wait_time:.0f}s", "SYSTEM")
                time.sleep(wait_time)
                now = time.time()
            # Rate limit ปกติ
            elapsed = now - self._last_request
            if elapsed < self._min_interval:
                jitter = random.uniform(0.5, 1.5)
                wait_time = self._min_interval - elapsed + jitter
                time.sleep(wait_time)
            self._last_request = time.time()

    def trigger_backoff(self, seconds: float = 120.0, worker_tag: str = ""):
        """เรียกเมื่อสงสัยว่าโดน IP block — ทุก worker หยุดยาว"""
        with self._lock:
            self._backoff_until = time.time() + seconds
            status(0, 0, f"[{worker_tag}] IP block detected — backoff {seconds:.0f}s for ALL workers", "SYSTEM")


def _is_ip_blocked(page) -> bool:
    """ตรวจจับว่าโดน IP block / rate limit (403, 429, Cloudflare block)"""
    try:
        title = page.title().lower()
        content = page.locator("body").inner_text(timeout=2000).lower()
        # Cloudflare block / Access denied
        if any(x in title for x in ["access denied", "just a moment", "attention required"]):
            return True
        if any(x in content for x in ["403 forbidden", "429 too many requests",
                                        "access denied", "you have been blocked",
                                        "rate limit", "ip has been"]):
            return True
    except Exception:
        pass
    return False


def _run_worker(
    worker_id: int,
    account_queue: Queue,
    results_list: list,
    results_lock: threading.Lock,
    args,
    activity,
    total: int,
    use_agent: bool,
    screenshot_dir,
    initial_cookies: list,
    rate_limiter: _RateLimiter = None,
    proxy: dict = None,
    viewport: dict = None,
):
    """Worker thread: สร้าง browser context ของตัวเอง แล้วดึงบัญชีจาก queue ทีละตัว"""
    if viewport is None:
        viewport = _get_viewport()
    from playwright.sync_api import sync_playwright

    import shutil

    worker_tag = f"W{worker_id}"
    sandbox_dir = PROJECT_ROOT / f".chrome_parallel/w{worker_id}"
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    # ก๊อป settings จาก .chrome_profile ที่ User ตั้งค่าไว้แล้ว
    # โครงสร้าง Chrome: user_data_dir/Local State (root) + user_data_dir/Default/Preferences (profile)
    source_profile = PROJECT_ROOT / ".chrome_profile"
    # Local State อยู่ที่ root
    src_ls = source_profile / "Local State"
    if src_ls.exists():
        try:
            shutil.copy2(src_ls, sandbox_dir / "Local State")
        except Exception:
            pass
    # Preferences อยู่ใน Default/
    default_dir = sandbox_dir / "Default"
    default_dir.mkdir(parents=True, exist_ok=True)
    source_default = source_profile / "Default"
    for pref_file in ("Preferences", "Secure Preferences"):
        src = source_default / pref_file
        if src.exists():
            try:
                shutil.copy2(src, default_dir / pref_file)
            except Exception:
                pass

    # Force-patch Default/Preferences เพื่อปิด password popup + leak warning ให้ชัวร์
    prefs_path = default_dir / "Preferences"
    try:
        prefs = {}
        if prefs_path.exists():
            with open(prefs_path, "r", encoding="utf-8") as f:
                prefs = json.load(f)
        # ปิด "Save password?" popup
        prefs["credentials_enable_service"] = False
        prefs["credentials_enable_autosign_in"] = False
        prefs.setdefault("profile", {})["password_manager_enabled"] = False
        pm = prefs.setdefault("password_manager", {})
        pm["offer_to_save_passwords"] = False
        pm["password_manager_enabled"] = False
        pm["credentials_enable_service"] = False
        # ปิด "password was compromised in a data breach" warning
        prefs.setdefault("profile", {})["password_manager_leak_detection"] = False
        pm["leak_detection"] = False
        with open(prefs_path, "w", encoding="utf-8") as f:
            json.dump(prefs, f)
    except Exception:
        pass

    with sync_playwright() as p:
        # --- Browser setup (เหมือน main แต่ใช้ sandbox แยก) ---
        browser_exe = None
        browser_type = args.browser
        if args.use_chrome:
            browser_type = "chrome"

        if browser_type == "chrome":
            for path in [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                str(Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe"),
            ]:
                if Path(path).exists():
                    browser_exe = path
                    break
        elif browser_type == "msedge":
            for path in [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ]:
                if Path(path).exists():
                    browser_exe = path
                    break

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            f"--window-size={viewport['width']},{viewport['height']}",
            "--disable-session-crashed-bubble",
            "--disable-restore-session-state",
            "--no-first-run",
            "--disable-features=PasswordCheck,PasswordLeakDetection,PasswordImport,PasswordGeneration",
            "--password-store=basic",
            "--disable-save-password-bubble",
            "--disable-translate",
            "--disable-infobars",
            "--disable-notifications",
            "--disable-popup-blocking",
            "--disable-default-apps",
            "--no-default-browser-check",
        ]
        ignore_args = ["--enable-automation"]

        engine = p.chromium
        channel = None
        if browser_type == "msedge":
            channel = "msedge"
        elif browser_type == "chrome":
            if not browser_exe:
                channel = "chrome"

        launch_kwargs = dict(
            user_data_dir=str(sandbox_dir),
            executable_path=browser_exe,
            channel=channel,
            headless=args.headless,
            slow_mo=50 if use_agent else 0,
            args=launch_args,
            ignore_default_args=ignore_args,
            viewport=viewport,
            user_agent=USER_AGENT,
            locale="th-TH",
            timezone_id="Asia/Bangkok",
        )
        if proxy:
            launch_kwargs["proxy"] = proxy

        try:
            context = engine.launch_persistent_context(**launch_kwargs)
        except Exception as e:
            status(0, 0, f"[{worker_tag}] ❌ เปิด browser ไม่ได้: {e}", "SYSTEM")
            return

        proxy_info = f" via {proxy['server']}" if proxy else ""
        status(0, 0, f"[{worker_tag}] browser พร้อม{proxy_info} (sandbox: .chrome_parallel/w{worker_id}/)", "SYSTEM")

        try:
            # --- Load initial cookies ---
            if initial_cookies:
                try:
                    context.add_cookies(initial_cookies)
                except Exception:
                    pass

            # --- Anti-bot break state per worker ---
            # แต่ละ worker สุ่ม offset ต่างกัน เพื่อไม่ให้พักพร้อมกัน
            accounts_since_break = 0
            break_offset = worker_id * 3  # W0=+0, W1=+3, W2=+6 ...
            next_break_at = random.randint(8 + break_offset, 15 + break_offset)

            while True:
                try:
                    i_run, exe_id, password = account_queue.get_nowait()
                except Empty:
                    break  # queue empty

                # --- Anti-bot break ---
                if accounts_since_break >= next_break_at:
                    wait_time = random.randint(30, 60)
                    status(i_run, total, f"[{worker_tag}] ☕ พักเบรก {wait_time}s...", "SYSTEM")
                    time.sleep(wait_time)
                    accounts_since_break = 0
                    next_break_at = random.randint(8 + break_offset, 15 + break_offset)

                # --- Cookie cleanup ---
                try:
                    all_cookies = context.cookies()
                    cf_cookies = [
                        c for c in all_cookies
                        if "cf" in c["name"].lower() or "turnstile" in c["name"].lower() or "google" in c["domain"]
                    ]
                    context.clear_cookies()
                    if cf_cookies:
                        context.add_cookies(cf_cookies)
                except Exception:
                    context.clear_cookies()

                if initial_cookies:
                    try:
                        context.add_cookies(initial_cookies)
                    except Exception:
                        pass

                status(i_run, total, f"[{worker_tag}] กำลังล็อกอิน ...", exe_id)

                # Rate limit: รอคิวก่อนยิง request
                if rate_limiter:
                    rate_limiter.wait(worker_tag)

                max_retries = min(3, max(0, getattr(args, "max_retries", 1)))
                final_result = None

                for attempt in range(max_retries + 1):
                    page = context.new_page()
                    if use_agent:
                        hide_automation(page)

                    try:
                        flow_res = run_login_flow(
                            page,
                            exe_id,
                            password,
                            i_run,
                            total,
                            args.login_url,
                            activity,
                            use_agent=use_agent,
                            human_type=args.human_type if use_agent else False,
                            screenshot_dir=screenshot_dir,
                            preview_mode=False,  # preview ไม่รองรับ parallel
                        )

                        if flow_res.get("error"):
                            err_msg = flow_res["error"]

                            # ตรวจจับ IP block — trigger backoff ยาวให้ทุก worker
                            if rate_limiter and _is_ip_blocked(page):
                                status(i_run, total, f"[{worker_tag}] IP BLOCKED — หยุดยาว 120s", exe_id)
                                rate_limiter.trigger_backoff(120.0, worker_tag)

                            if attempt < max_retries and should_retry(err_msg):
                                delay = get_retry_delay(err_msg)
                                status(i_run, total, f"[{worker_tag}] ⚠️ Retry {attempt + 1}/{max_retries} (รอ {delay}s): {err_msg[:50]}...", exe_id)
                                page.close()
                                time.sleep(delay)
                                continue

                            is_bad_cred = not should_retry(err_msg)
                            if is_bad_cred:
                                status(i_run, total, f"[{worker_tag}] ❌ รหัสผิด — ข้าม: {exe_id}", exe_id)
                            else:
                                status(i_run, total, f"[{worker_tag}] Error: {err_msg}", exe_id)
                            final_result = {
                                "id": exe_id,
                                "status": False,
                                "message": err_msg if attempt == 0 else f"{err_msg} (หลัง {attempt} retry)",
                                "screenshot": flow_res.get("screenshot"),
                                "time": datetime.now().strftime("%H:%M:%S"),
                                "extra": flow_res.get("extra_data", {}),
                                "bad_credentials": is_bad_cred,
                            }
                        else:
                            msg = "สำเร็จและ Log out แล้ว"
                            if attempt > 0:
                                msg = f"สำเร็จ (retry ครั้งที่ {attempt})"
                            status(i_run, total, f"[{worker_tag}] {msg}", exe_id)
                            final_result = {
                                "id": exe_id,
                                "status": True,
                                "message": "Success" if attempt == 0 else f"Success (retry {attempt})",
                                "screenshot": flow_res.get("screenshot"),
                                "time": datetime.now().strftime("%H:%M:%S"),
                                "extra": flow_res.get("extra_data", {}),
                            }

                        page.close()
                        break

                    except Exception as e:
                        err_msg = f"[Critical] {str(e)[:100]}"
                        page.close()

                        if attempt < max_retries and should_retry(err_msg):
                            delay = get_retry_delay(err_msg)
                            status(i_run, total, f"[{worker_tag}] ⚠️ Retry {attempt + 1}/{max_retries} (รอ {delay}s): {err_msg[:50]}...", exe_id)
                            time.sleep(delay)
                            continue

                        status(i_run, total, f"[{worker_tag}] Error: {err_msg}", exe_id)
                        final_result = {
                            "id": exe_id,
                            "status": False,
                            "message": err_msg if attempt == 0 else f"{err_msg} (หลัง {attempt} retry)",
                            "screenshot": None,
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "extra": {},
                        }
                        break

                if final_result:
                    with results_lock:
                        results_list.append(final_result)
                    prog_entry = {"index": i_run, "id": exe_id, "status": final_result["status"], "time": final_result["time"]}
                    if final_result.get("bad_credentials"):
                        prog_entry["bad_credentials"] = True
                    save_progress(prog_entry, total, activity.id, str(args.file))

                accounts_since_break += 1
                account_queue.task_done()

        finally:
            context.close()
            status(0, 0, f"[{worker_tag}] ปิด browser แล้ว", "SYSTEM")


def _run_parallel(args, activity, accounts_to_run, start_idx, total, use_agent, screenshot_dir, initial_cookies, viewport=None):
    """Parallel orchestrator: สร้าง queue, ปล่อย N worker threads, รวมผลลัพธ์"""
    if viewport is None:
        viewport = _get_viewport()
    n_workers = args.parallel
    account_queue = Queue()

    for i_run, (exe_id, password) in enumerate(accounts_to_run, start=start_idx):
        account_queue.put((i_run, exe_id, password))

    results = []
    results_lock = threading.Lock()
    run_start_time = datetime.now()

    # โหลด proxies (ถ้ามี)
    proxies = _load_proxies(getattr(args, "proxy_file", None))
    if proxies:
        status(0, 0, f"Proxy: {len(proxies)} proxy loaded — จะแจก round-robin ให้ {n_workers} workers", "SYSTEM")
        for i, px in enumerate(proxies):
            status(0, 0, f"  Proxy {i}: {px['server']}", "SYSTEM")

    # Rate limiter: ถ้ามี proxy คนละ IP ไม่ต้องเว้นนานมาก
    if proxies and len(proxies) >= n_workers:
        min_interval = 2.0  # แต่ละ worker ใช้ IP ต่างกัน — เว้นแค่ 2s
        status(0, 0, f"Rate limit: {min_interval:.0f}s (proxy mode — แต่ละ worker คนละ IP)", "SYSTEM")
    else:
        min_interval = 4.0 + max(0, n_workers - 1) * 2.0
        status(0, 0, f"Rate limit: {min_interval:.0f}s ระหว่าง request (ทุก worker รวมกัน)", "SYSTEM")
    rate_limiter = _RateLimiter(min_interval=min_interval)

    init_progress(total, activity.id, str(args.file))
    status(0, 0, f"เริ่ม parallel mode: {n_workers} workers, {len(accounts_to_run)} บัญชี", "SYSTEM")

    threads = []
    for wid in range(n_workers):
        # Round-robin proxy: W0→proxy[0], W1→proxy[1], ...
        worker_proxy = proxies[wid % len(proxies)] if proxies else None
        t = threading.Thread(
            target=_run_worker,
            args=(wid, account_queue, results, results_lock, args, activity, total, use_agent, screenshot_dir, initial_cookies, rate_limiter, worker_proxy, viewport),
            daemon=True,
        )
        threads.append(t)
        t.start()
        # Stagger start: worker ถัดไปออกตัวช้ากว่า เพื่อไม่ให้ยิง server พร้อมกัน
        if wid < n_workers - 1:
            stagger = random.uniform(1.0, 3.0)
            status(0, 0, f"Worker {wid} started, รอ {stagger:.1f}s ก่อนปล่อย worker ถัดไป", "SYSTEM")
            time.sleep(stagger)

    for t in threads:
        t.join()

    run_end_time = datetime.now()

    # เรียงผลลัพธ์ตาม id เพื่อให้ report อ่านง่าย
    results.sort(key=lambda r: r["id"])

    if results:
        generate_reports(results, run_start_time, run_end_time, activity_id=activity.id, activity=activity)
        hist_file = save_run_history(results, run_start_time, run_end_time, activity.id, str(args.file))
        print(f"[History] บันทึกประวัติ: {hist_file}", flush=True)

    clear_progress()
    print("---", flush=True)
    print(f"เสร็จสิ้นทุกบัญชี — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    return 0


def _get_screen_size() -> tuple[int, int]:
    """Auto-detect screen resolution, capped for browser viewport."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        if w >= 800 and h >= 600:
            return (w, h)
    except Exception:
        pass
    try:
        import subprocess
        out = subprocess.check_output(
            ["python", "-c", "import tkinter;r=tkinter.Tk();print(r.winfo_screenwidth(),r.winfo_screenheight());r.destroy()"],
            timeout=5, text=True
        ).strip()
        w, h = map(int, out.split())
        if w >= 800 and h >= 600:
            return (w, h)
    except Exception:
        pass
    return (1920, 1080)


def _get_viewport() -> dict:
    """Get browser viewport size — slightly smaller than screen to fit in window."""
    w, h = _get_screen_size()
    # Leave room for taskbar and window chrome
    vw = min(w - 40, 1920)
    vh = min(h - 120, 1080)
    return {"width": max(vw, 800), "height": max(vh, 600)}


def _find_account_file(default_path: Path) -> Path | None:
    """ถ้า default ไม่มี ให้หาไฟล์ .txt ที่มี format exe_id,password ในโฟลเดอร์เดียวกัน"""
    search_dir = default_path.parent if default_path.parent != Path() else Path(".")
    skip = {"requirements.txt", "proxies.txt"}
    for txt in sorted(search_dir.glob("*.txt")):
        if txt.name.lower() in skip:
            continue
        try:
            with open(txt, encoding="utf-8") as f:
                first_lines = [l.strip() for l in f.readlines()[:5] if l.strip() and not l.startswith("#")]
            if first_lines and all("," in l for l in first_lines):
                return txt
        except Exception:
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EXE Portal login automation (Login -> ไปหน้ากิจกรรม -> รอ -> Logout per account)."
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("IDGE.txt"),
        help="Path to accounts file (exe_id,password per line). Default: IDGE.txt",
    )
    parser.add_argument("--headless", action="store_true", help="Run browser headless.")
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Keep browser open after all accounts (for debugging).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only load accounts and print what would be done (no browser).",
    )
    parser.add_argument(
        "--login-url",
        type=str,
        default=LOGIN_URL_DEFAULT,
        help=f"Login page URL. Default: {LOGIN_URL_DEFAULT} (use {LOGIN_URL_LEGACY} for legacy).",
    )
    parser.add_argument(
        "--activity",
        type=str,
        default=ACTIVITY_ID_DEFAULT,
        help=f"รหัสกิจกรรม (จาก module ใน activities/). Default: {ACTIVITY_ID_DEFAULT}. ใช้ --list-activities แสดงรายการ.",
    )
    parser.add_argument(
        "--list-activities",
        action="store_true",
        help="แสดงรายการกิจกรรมที่ลงทะเบียนแล้ว แล้วจบ",
    )
    parser.add_argument(
        "--no-agent",
        action="store_true",
        help="ปิดโหมด agent (ไม่ซ่อน automation, ไม่รอแบบสุ่ม — ใช้เมื่อต้องการรันเร็ว).",
    )
    parser.add_argument(
        "--human-type",
        action="store_true",
        help="พิมพ์ทีละตัวแบบคน (ช้ากว่า แต่ดูเป็นธรรมชาติมากขึ้น). ใช้กับโหมด agent.",
    )
    parser.add_argument(
        "--screenshots-dir",
        type=Path,
        default=Path("screenshots"),
        help="โฟลเดอร์เก็บรูปหน้าจอกิจกรรมต่อไอดีเกม (default: screenshots). ปิดได้ด้วย --no-screenshots.",
    )
    parser.add_argument(
        "--no-screenshots",
        action="store_true",
        help="ไม่ถ่ายรูปหน้าจอกิจกรรม",
    )
    parser.add_argument(
        "--item-code",
        type=str,
        help="Item Code ที่ต้องการเติม (รูปแบบ QNAN-CP99-17FB-2DU8)",
    )
    parser.add_argument(
        "--cookies",
        type=Path,
        help="Path ไปยังไฟล์ cookies.json (Export จากบราว์เซอร์จริงเพื่อ Bypass Cloudflare)",
    )
    parser.add_argument(
        "--use-chrome",
        action="store_true",
        help="ใช้ Google Chrome ที่ติดตั้งในเครื่องแทน Chromium ของ Playwright (Deprecating: use --browser chrome instead)",
    )
    parser.add_argument(
        "--browser",
        type=str,
        default="chrome",
        choices=["chrome", "msedge", "chromium"],
        help="เลือกเบราว์เซอร์ที่จะใช้รัน (chrome, msedge, chromium)",
    )
    parser.add_argument(
        "--use-default-browser-cookies",
        action="store_true",
        help="โหลด cookies จาก Chrome หลักของเครื่องมาใช้ (ช่วยให้ Cloudflare ผ่าน — บน Windows ควรปิด Chrome ก่อน)",
    )
    parser.add_argument(
        "--chrome-user-data",
        type=Path,
        default=None,
        help="ใช้ Chrome profile จริงของเครื่อง (ต้องปิด Chrome ก่อน) — ใช้เมื่อกดยืนยันมนุษย์ในเบราว์เซอร์สคริปต์ไม่ผ่าน",
    )
    parser.add_argument(
        "--keep-browser-settings",
        action="store_true",
        help="ใช้ Sandbox Profile ที่ User ตั้งค่าไว้แล้ว (ไม่ Clone ใหม่ทับ)",
    )

    parser.add_argument(
        "--start-index",
        type=int,
        default=1,
        help="เริ่มรันที่บัญชีลำดับที่กำหนด (ลำดับในไฟล์เริ่มที่ 1)",
    )
    parser.add_argument(
        "--stop-index",
        type=int,
        default=0,
        help="หยุดรันที่บัญชีลำดับที่กำหนด (ลำดับในไฟล์เริ่มที่ 1, 0 = รันจนจบไฟล์)",
    )
    parser.add_argument(
        "--overwrite-url",
        type=str,
        help="URL กิจกรรมที่จะใช้แทน URL เดิม (สำหรับกิจกรรมที่เปลี่ยนลิงก์ทุกเดือน)",
    )
    parser.add_argument(
        "--ny-sets",
        type=str,
        default="",
        help="รายการเซตการ์ดที่ต้องการเปิด (เช่น 1,2,5) สำหรับกิจกรรม New Year 2026",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="จำนวนครั้งที่จะ retry เมื่อล้มเหลว (0-3, ไม่รวมรหัสผิด)",
    )
    parser.add_argument(
        "--preview-mode",
        action="store_true",
        help="บันทึก screenshot ระหว่างทำงานลง .preview/ เพื่อให้ UI แสดงผล",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="จำนวน worker ที่รันพร้อมกัน (1-5, default: 1 = sequential). แต่ละ worker ใช้ browser context แยก.",
    )
    parser.add_argument(
        "--proxy-file",
        type=Path,
        default=None,
        help="ไฟล์รายการ proxy (1 บรรทัด/proxy, รูปแบบ: host:port หรือ user:pass@host:port หรือ socks5://host:port)",
    )
    args = parser.parse_args()
    args.parallel = max(1, min(5, args.parallel))

    if args.list_activities:
        print("กิจกรรมที่ลงทะเบียน:")
        for a in list_activities():
            print(f"  --activity {a.id}  ({a.name})")
        return 0

    activity = get_activity(args.activity)
    if not activity:
        print(f"Error: ไม่พบกิจกรรม id '{args.activity}'", file=sys.stderr)
        print("ใช้ --list-activities แสดงรายการ", file=sys.stderr)
        return 1

    if not args.file.exists():
        # Auto-detect: ถ้า default IDGE.txt ไม่มี ให้หาไฟล์ .txt ที่มี format exe_id,password
        found = _find_account_file(args.file)
        if found:
            print(f"[Auto] ไม่พบ {args.file.name} — ใช้ {found.name} แทน")
            args.file = found
        else:
            txt_files = [f.name for f in Path(".").glob("*.txt") if f.name.lower() not in ("requirements.txt", "proxies.txt")]
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            if txt_files:
                print(f"  Available .txt files: {', '.join(txt_files)}", file=sys.stderr)
                print(f"  Use: --file <filename>", file=sys.stderr)
            else:
                print(f"  Create a file with accounts (format: exe_id,password per line)", file=sys.stderr)
            return 1

    accounts = load_accounts(args.file)
    if not accounts:
        print("Error: No valid accounts in file (format: exe_id,password per line).", file=sys.stderr)
        return 1

    if args.overwrite_url:
        print(f"[Config] Overwriting activity URL to: {args.overwrite_url}")
        activity.url = args.overwrite_url

    total = len(accounts)
    
    # กรองบัญชีตามจุดเริ่มต้นและจุดสิ้นสุดที่กำหนด
    start_idx = max(1, args.start_index)
    stop_idx = args.stop_index if args.stop_index > 0 else total
    stop_idx = min(stop_idx, total)

    if start_idx > total:
        print(f"Error: ลำดับที่เริ่ม ({start_idx}) มากกว่าจำนวนบัญชีที่มีทั้งหมด ({total})", file=sys.stderr)
        return 1
    
    if start_idx > stop_idx:
        print(f"Error: ลำดับที่เริ่ม ({start_idx}) ต้องไม่มากกว่าลำดับที่หยุด ({stop_idx})", file=sys.stderr)
        return 1
        
    accounts_to_run = accounts[start_idx-1:stop_idx]
    
    # Auto-detect viewport size
    viewport = _get_viewport()
    vp_str = f"{viewport['width']}x{viewport['height']}"

    print(f"Loaded {total} account(s) from {args.file} (รันลำดับที่ {start_idx} ถึง {stop_idx})", flush=True)
    print(f"กิจกรรม: {activity.name} (--activity {activity.id})", flush=True)
    
    if args.item_code:
        activity.extra_data = {"item_code": args.item_code}
        print(f"Item Code: {args.item_code}")
    
    if args.ny_sets:
        if not activity.extra_data: activity.extra_data = {}
        activity.extra_data["ny_sets"] = [int(s) for s in args.ny_sets.split(",") if s.strip().isdigit()]
        print(f"New Year Sets: {activity.extra_data['ny_sets']}")

    if activity and "itemcode" in getattr(activity, "id", ""):
        if getattr(args, "chrome_user_data", None):
            print("กิจกรรม itemcode: ใช้ Chrome profile จริง — กรุณาปิด Chrome ทั้งหมดก่อนรัน", flush=True)
        else:
            print("กิจกรรม itemcode: บัญชีแรกถ้าเจอ Cloudflare — กดยืนยันมนุษย์ในหน้าต่างเบราว์เซอร์ที่สคริปต์เปิด สคริปต์จะเก็บ cookie ไว้ใช้บัญชีถัดไป", flush=True)

    screenshot_dir = None if args.no_screenshots else args.screenshots_dir
    if screenshot_dir:
        print(f"เก็บรูปหน้าจอกิจกรรมที่: {screenshot_dir}/<activity_id>/<exe_id>_<timestamp>.png")

    if args.dry_run:
        print("(dry-run: ไม่เปิดเบราว์เซอร์)")
        for i_run, (exe_id, _) in enumerate(accounts_to_run, start=start_idx):
            # จำลองขั้นตอนที่เกิดขึ้นจริงใน login_flow.py
            steps = ["เข้าหน้ากิจกรรม", "ล็อกอิน (ถ้ามี)", "รอกิจกรรม", "ออกจากระบบ"]
            flow_summary = " -> ".join(steps)
            status(i_run, stop_idx, f"จะทำ: {flow_summary} ({activity.name} / รอ {activity.wait_seconds}s)", exe_id)
        print("เสร็จสิ้นทุกบัญชี (dry-run)")
        return 0

    use_agent = not args.no_agent
    if use_agent:
        print("โหมด agent: เปิด (เบราว์เซอร์และพฤติกรรมคล้ายคนใช้ — ลดโอกาสถูก Cloudflare บล็อก)", flush=True)

    headless_note = " (headless — ดูความคืบหน้าจากข้อความด้านล่าง)" if args.headless else ""
    parallel_note = f" (parallel x{args.parallel})" if args.parallel > 1 else ""
    print(f"เริ่มรัน {datetime.now().strftime('%H:%M:%S')}{headless_note}{parallel_note}", flush=True)
    print("---", flush=True)

    # ===== Parallel mode =====
    if args.parallel > 1:
        # โหลด cookies จากไฟล์ (ถ้ามี) เพื่อส่งให้แต่ละ worker
        parallel_cookies = []
        if args.cookies and args.cookies.exists():
            try:
                with open(args.cookies, "r", encoding="utf-8") as f:
                    cookies_data = json.load(f)
                    if not isinstance(cookies_data, list):
                        cookies_data = [cookies_data]
                    for c in cookies_data:
                        item = {
                            "name": c.get("name"),
                            "value": c.get("value"),
                            "domain": c.get("domain"),
                            "path": c.get("path", "/"),
                            "secure": c.get("secure", True),
                        }
                        ss = str(c.get("sameSite", "Lax")).capitalize()
                        item["sameSite"] = ss if ss in ["Strict", "Lax", "None"] else "Lax"
                        if "expirationDate" in c:
                            item["expires"] = float(c["expirationDate"])
                        parallel_cookies.append(item)
                print(f"[Cookies] Loaded {len(parallel_cookies)} cookies for parallel workers.", flush=True)
            except Exception as e:
                print(f"Warning: Cookies error: {str(e)[:50]}", flush=True)
        return _run_parallel(args, activity, accounts_to_run, start_idx, stop_idx, use_agent, screenshot_dir, initial_cookies=parallel_cookies, viewport=viewport)

    with sync_playwright() as p:
        # 1. ค้นหา Path ของเบราว์เซอร์จริงใน Windows
        browser_exe = None
        browser_type = args.browser
        
        # Legacy support: if --use-chrome is set, use chrome
        if args.use_chrome:
            browser_type = "chrome"

        if browser_type == "chrome":
            paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                str(Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe")
            ]
            for path in paths:
                if Path(path).exists():
                    browser_exe = path
                    break
        elif browser_type == "msedge":
            paths = [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
            ]
            for path in paths:
                if Path(path).exists():
                    browser_exe = path
                    break


        # 2. ตั้งค่า Launch Options แบบรวมรวบสุดยอด (Stealth + Real Chrome)
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            f"--window-size={viewport['width']},{viewport['height']}",
            "--disable-session-crashed-bubble",
            "--disable-restore-session-state",
            "--no-first-run",

            # ปิด Password Manager Popups (Change your password, Save password, etc.)
            "--disable-features=PasswordCheck,PasswordLeakDetection,PasswordImport,PasswordGeneration",
            "--password-store=basic",
            "--disable-save-password-bubble",

            # ปิด Popups อื่นๆ ที่น่ารำคาญ
            "--disable-translate",
            "--disable-infobars",
            "--disable-notifications",
            "--disable-popup-blocking",
            "--disable-default-apps",
            "--no-default-browser-check",
        ]

        
        # ใส่กลับคืน: ซ่อนแถบ Automation จะช่วยให้ Playwright เชื่อมต่อได้เสถียรกว่าในบางเคส
        ignore_args = ["--enable-automation"]

        context = None # Initialize context to None
        try:
            # --- โหมด Persistent — ใช้ profile จริงของ Chrome ได้ (Modern Clone Approach) ---
            user_data_dir = PROJECT_ROOT / ".chrome_profile"
            sandbox_dir = PROJECT_ROOT / ".chrome_sandbox"
            
            if getattr(args, "chrome_user_data", None) and args.chrome_user_data:
                source_path = Path(args.chrome_user_data)
                
                # ถ้า User เลือก Keep Browser Settings และ Sandbox มีอยู่แล้ว ให้ข้าม Clone
                if getattr(args, "keep_browser_settings", False) and sandbox_dir.exists():
                    print(f"✅ โหมด Keep Settings: ใช้ Sandbox ที่ตั้งค่าไว้แล้ว", flush=True)
                    user_data_dir = sandbox_dir
                else:
                    # ทำการ Clone Profile ไปที่ Sandbox เพื่อเลี่ยงการติด Lock
                    _clone_profile(source_path, sandbox_dir)
                    user_data_dir = sandbox_dir
                    print(f"✅ โหมด Sandbox: ใช้ข้อมูลจาก {source_path.name}", flush=True)
            elif getattr(args, "keep_browser_settings", False) and sandbox_dir.exists():
                # ถ้าไม่ได้ระบุ chrome_user_data แต่มี sandbox อยู่แล้ว ให้ใช้ sandbox
                print(f"✅ โหมด Keep Settings: ใช้ Sandbox ที่ตั้งค่าไว้แล้ว", flush=True)
                user_data_dir = sandbox_dir


            
            status(0, 0, "กำลังเตรียมระบบเบราว์เซอร์...", "SYSTEM")
            
            # กำหนด Browser Engine และ Channel
            engine = p.chromium
            channel = None
            
            if browser_type == "msedge":
                channel = "msedge"
            elif browser_type == "chrome":
                if not browser_exe: channel = "chrome"
            
            # สร้าง Context (แทนการสร้าง Browser แยก)
            seq_launch_kwargs = dict(
                user_data_dir=str(user_data_dir),
                executable_path=browser_exe,
                channel=channel,
                headless=args.headless,
                slow_mo=50 if use_agent else 0,
                args=launch_args,
                ignore_default_args=ignore_args,
                viewport=viewport,
                user_agent=USER_AGENT,
                locale="th-TH",
                timezone_id="Asia/Bangkok",
            )
            # Proxy support (sequential mode ใช้ proxy ตัวแรกจากไฟล์)
            seq_proxies = _load_proxies(getattr(args, "proxy_file", None))
            if seq_proxies:
                seq_launch_kwargs["proxy"] = seq_proxies[0]
                status(0, 0, f"Proxy: {seq_proxies[0]['server']}", "SYSTEM")

            context = engine.launch_persistent_context(**seq_launch_kwargs)
            status(0, 0, "ระบบพร้อมทำงาน!", "SYSTEM")
            status(0, 0, "เบราว์เซอร์พร้อมแล้ว เริ่มรันบัญชี...", "SYSTEM")

            # โหลด Cookies เริ่มต้น (จากไฟล์หรือ Chrome)
            # ⚠️ สำคัญ: ถ้าใช้ chrome_user_data (Profile จริง) ห้ามโหลด cookies ซ้ำซ้อนเพราะจะเกิด File Lock Conflict
            initial_cookies = []
            if not getattr(args, "chrome_user_data", None):
                if args.cookies and args.cookies.exists():
                    try:
                        with open(args.cookies, 'r', encoding='utf-8') as f:
                            cookies_data = json.load(f)
                            if not isinstance(cookies_data, list):
                                cookies_data = [cookies_data]
                            for c in cookies_data:
                                item = {
                                    "name": c.get("name"),
                                    "value": c.get("value"),
                                    "domain": c.get("domain"),
                                    "path": c.get("path", "/"),
                                    "secure": c.get("secure", True)
                                }
                                ss = str(c.get("sameSite", "Lax")).capitalize()
                                item["sameSite"] = ss if ss in ["Strict", "Lax", "None"] else "Lax"
                                if "expirationDate" in c:
                                    item["expires"] = float(c["expirationDate"])
                                initial_cookies.append(item)
                            context.add_cookies(initial_cookies)
                            print(f"[Cookies] Loaded {len(initial_cookies)} cookies from file.", flush=True)
                    except Exception as e:
                        print(f"Warning: Cookies error: {str(e)[:50]}", flush=True)

                if not initial_cookies and getattr(args, "use_default_browser_cookies", False):
                    try:
                        initial_cookies = get_chrome_cookies_for_playwright([".exe.in.th", "itemcode.exe.in.th", "passport.exe.in.th"])
                        if initial_cookies:
                            print(f"[Cookies] โหลดจาก Chrome หลักได้ {len(initial_cookies)} คุกกี้.", flush=True)
                            context.add_cookies(initial_cookies)
                    except Exception as e:
                        print(f"Warning: โหลด cookies จาก Chrome ไม่ได้: {e}", flush=True)
            else:
                if getattr(args, "use_default_browser_cookies", False) or args.cookies:
                    print("[System] โหมด Profile จริง: ข้ามการโหลด Cookies ซ้ำซ้อนเพื่อป้องกันไฟล์ถูกล็อค", flush=True)

            # กิจกรรม itemcode: เก็บ cf_clearance จากเบราว์เซอร์ที่สคริปต์เปิด (หลังคุณกดยืนยันมนุษย์ในหน้าต่างนั้น) ไว้ใช้บัญชีถัดไป
            is_itemcode = activity and "itemcode" in getattr(activity, "id", "")

            # เริ่มรันแต่ละไอดี
            results = []
            run_start_time = datetime.now()
            init_progress(stop_idx, activity.id, str(args.file))
            
            # --- ตั้งค่าสำหรับการพัก (Anti-Bot Break) ---
            accounts_since_break = 0
            # สุ่มว่าจะพักทุกๆ กี่ไอดี (เช่น 8-15 ไอดีพักทีหนึ่ง)
            next_break_at = random.randint(8, 15)
            
            for i_run, (exe_id, password) in enumerate(accounts_to_run, start=start_idx):
                # --- ตรรกะการหยุดพัก ---
                if accounts_since_break >= next_break_at:
                    wait_time = random.randint(30, 60)
                    status(i_run, stop_idx, f"☕ ช่วงพักเบรก! พักสายตา {wait_time} วินาที ก่อนเริ่มกลุ่มถัดไป...", "SYSTEM")
                    import time
                    for remaining in range(wait_time, 0, -1):
                        if remaining % 10 == 0 or remaining <= 5:
                            status(i_run, stop_idx, f"☕ กำลังพักเบรก... อีก {remaining} วินาทีจะเริ่มต่อ", "SYSTEM")
                        time.sleep(1)

                    # รีเซ็ตค่าสุ่มใหม่
                    accounts_since_break = 0
                    next_break_at = random.randint(8, 15)
                    status(i_run, stop_idx, "✅ พักเสร็จแล้ว! ลุยต่อ...", "SYSTEM")

                # --- จัดการ Cookies ก่อนเริ่มไอดีใหม่ ---
                # ⚠️ เราจะไม่ลบหมด แต่จะลบเฉพาะที่เกี่ยวกับ Login เพื่อรักษา Cloudflare Clearance ไว้
                try:
                    all_cookies = context.cookies()
                    # เก็บเฉพาะคุ๊กกี้ของ Cloudflare และความปลอดภัย
                    cf_cookies = [c for c in all_cookies if "cf" in c['name'].lower() or "turnstile" in c['name'].lower() or "google" in c['domain']]
                    
                    context.clear_cookies() # ล้างทั้งหมดก่อน
                    if cf_cookies:
                        context.add_cookies(cf_cookies) # ใส่ของ Cloudflare กลับเข้าไป
                        status(i_run, stop_idx, f"[System] Preserved {len(cf_cookies)} security cookies.", exe_id)
                except Exception:
                    context.clear_cookies()
                
                if initial_cookies:
                    try:
                        context.add_cookies(initial_cookies)
                    except Exception:
                        pass
 
                status(i_run, stop_idx, "กำลังล็อกอิน ...", exe_id)
                
                max_retries = min(3, max(0, getattr(args, 'max_retries', 1)))  # Clamp 0-3
                flow_res = None
                final_result = None
                
                for attempt in range(max_retries + 1):
                    page = context.new_page()
                    if use_agent:
                        hide_automation(page)
                    
                    try:
                        flow_res = run_login_flow(
                            page,
                            exe_id,
                            password,
                            i_run,
                            stop_idx,
                            args.login_url,
                            activity,
                            use_agent=use_agent,
                            human_type=args.human_type if use_agent else False,
                            screenshot_dir=screenshot_dir,
                            preview_mode=getattr(args, 'preview_mode', False),
                        )

                        # Save preview screenshot if enabled
                        if getattr(args, 'preview_mode', False):
                            save_preview(page)

                        if flow_res.get("error"):
                            err_msg = flow_res["error"]

                            # Check if should retry
                            if attempt < max_retries and should_retry(err_msg):
                                delay = get_retry_delay(err_msg)
                                status(i_run, stop_idx, f"⚠️ Retry {attempt + 1}/{max_retries} (รอ {delay}s): {err_msg[:50]}...", exe_id)
                                page.close()
                                import time
                                time.sleep(delay)
                                continue

                            # No more retries or non-retryable error
                            is_bad_cred = not should_retry(err_msg)
                            if is_bad_cred:
                                status(i_run, stop_idx, f"❌ รหัสผิด — ข้าม: {exe_id}", exe_id)
                            else:
                                status(i_run, stop_idx, f"Error: {err_msg}", exe_id)
                            final_result = {
                                "id": exe_id,
                                "status": False,
                                "message": err_msg if attempt == 0 else f"{err_msg} (หลัง {attempt} retry)",
                                "screenshot": flow_res.get("screenshot"),
                                "time": datetime.now().strftime("%H:%M:%S"),
                                "extra": flow_res.get("extra_data", {}),
                                "bad_credentials": is_bad_cred,
                            }
                        else:
                            # Success
                            msg = "สำเร็จและ Log out แล้ว"
                            if attempt > 0:
                                msg = f"สำเร็จ (retry ครั้งที่ {attempt})"
                            status(i_run, stop_idx, msg, exe_id)
                            final_result = {
                                "id": exe_id,
                                "status": True,
                                "message": "Success" if attempt == 0 else f"Success (retry {attempt})",
                                "screenshot": flow_res.get("screenshot"),
                                "time": datetime.now().strftime("%H:%M:%S"),
                                "extra": flow_res.get("extra_data", {})
                            }
                        
                        page.close()
                        break  # Exit retry loop
                        
                    except Exception as e:
                        err_msg = f"[Critical] {str(e)[:100]}"
                        page.close()
                        
                        if attempt < max_retries and should_retry(err_msg):
                            delay = get_retry_delay(err_msg)
                            status(i_run, stop_idx, f"⚠️ Retry {attempt + 1}/{max_retries} (รอ {delay}s): {err_msg[:50]}...", exe_id)
                            import time
                            time.sleep(delay)
                            continue

                        status(i_run, stop_idx, f"Error: {err_msg}", exe_id)
                        final_result = {
                            "id": exe_id,
                            "status": False,
                            "message": err_msg if attempt == 0 else f"{err_msg} (หลัง {attempt} retry)",
                            "screenshot": None,
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "extra": {}
                        }
                        break  # Exit retry loop
                
                if final_result:
                    results.append(final_result)
                    prog_entry = {"index": i_run, "id": exe_id, "status": final_result["status"], "time": final_result["time"]}
                    if final_result.get("bad_credentials"):
                        prog_entry["bad_credentials"] = True
                    save_progress(prog_entry, stop_idx, activity.id, str(args.file))

                # นับไอดีเพิ่มเพื่อใช้คำนวณการพักเบรก
                accounts_since_break += 1

            run_end_time = datetime.now()
            # สร้างรายงานสรุปผล
            if results:
                generate_reports(results, run_start_time, run_end_time, activity_id=activity.id, activity=activity)
                hist_file = save_run_history(results, run_start_time, run_end_time, activity.id, str(args.file))
                print(f"[History] บันทึกประวัติ: {hist_file}", flush=True)

            clear_progress()
            print("---", flush=True)
            print(f"เสร็จสิ้นทุกบัญชี — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

        except Exception as e:
            err_str = str(e)
            if "Opening in existing browser session" in err_str or "Target page, context or browser has been closed" in err_str:
                print(f"\n❌ Fatal Error: ไม่สามารถเริ่มการทำงานของเบราว์เซอร์ได้", file=sys.stderr)
                print(f"เส้นทางที่ถูกล็อค: {user_data_dir}", file=sys.stderr)
                print(f"สาเหตุที่เป็นไปได้:", file=sys.stderr)
                print(f"1. มีหน้าต่าง Google Chrome หรือ Bot ตัวอื่นใช้ Profile นี้อยู่ (กรุณาปิดให้หมด)", file=sys.stderr)
                print(f"2. Chrome แอบรันอยู่เบื้องหลัง (ให้กดปุ่ม Kill Chrome ใน UI เพื่อช่วยปิด)", file=sys.stderr)
                print(f"3. มีไฟล์ 'SingletonLock' ค้างอยู่ในโฟลเดอร์ด้านบน (ต้องลบทิ้งด้วยตนเอง)", file=sys.stderr)
            else:
                print(f"Fatal error during launch: {e}", flush=True)
            return 1
        finally:
            if context: # Ensure context was created before trying to close
                if not args.keep_open:
                    context.close()
                else:
                    print("เบราว์เซอร์ยังเปิดอยู่ (--keep-open)")
                    input("กด Enter เพื่อปิดเบราว์เซอร์ ...")
                    context.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
