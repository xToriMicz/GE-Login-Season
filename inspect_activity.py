#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Activity Page Inspector — เปิดหน้ากิจกรรม login แล้ว dump selectors + screenshot
ให้ Claude ใช้สร้างกิจกรรมใหม่โดยไม่ต้องถาม user

Usage:
    python inspect_activity.py --url "https://activities2.exe.in.th/g/.../main"
    python inspect_activity.py --url "https://activities2.exe.in.th/g/.../main" --file IDGE.txt
    python inspect_activity.py --url "https://activities2.exe.in.th/g/.../main" --headless
"""

import argparse
import json
import sys
import io
import re
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

from core.config import LOGIN_URL_DEFAULT
from utils.accounts import load_accounts
from utils.agent import USER_AGENT, hide_automation, bypass_cloudflare, human_delay
from utils.console import status
from utils.navigation import safe_goto, wait_for_content

PROJECT_ROOT = Path(__file__).resolve().parent

# JS ที่ inject เข้าหน้าเว็บเพื่อ dump selectors ที่เกี่ยวข้อง
_INSPECT_JS = """
() => {
    const result = {
        buttons: [],
        points: [],
        forms: [],
        links: [],
        images: [],
        popups: [],
        texts: [],
        meta: {}
    };

    // 1. Buttons — ทุกปุ่มที่มองเห็น
    document.querySelectorAll('button, a.btn, [role="button"], input[type="submit"]').forEach(el => {
        if (el.offsetParent === null && !el.closest('.swal2-container')) return; // hidden
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) return;

        const info = {
            tag: el.tagName.toLowerCase(),
            text: (el.textContent || '').trim().substring(0, 100),
            id: el.id || null,
            classes: el.className || null,
            type: el.type || null,
            disabled: el.disabled || false,
            href: el.href || null,
            selector: _bestSelector(el),
        };
        result.buttons.push(info);
    });

    // 2. Point/Score elements — ตัวเลขที่น่าจะเป็นแต้ม
    document.querySelectorAll('[class*="point"], [class*="score"], [class*="energy"], [class*="coin"], [class*="counter"], [class*="balance"], [class*="credit"], [class*="treasure"], [class*="reward"], [class*="bonus"]').forEach(el => {
        if (el.offsetParent === null) return;
        const text = (el.textContent || '').trim();
        if (text.length > 200) return;
        result.points.push({
            text: text.substring(0, 100),
            selector: _bestSelector(el),
            classes: el.className || null,
            hasDigits: /\\d/.test(text),
        });
    });

    // 3. Login/Profile indicators
    document.querySelectorAll('.id-name, .logout-btn, .exe-profile, [class*="login"], [class*="profile"], [class*="user"]').forEach(el => {
        if (el.offsetParent === null) return;
        result.forms.push({
            text: (el.textContent || '').trim().substring(0, 100),
            selector: _bestSelector(el),
            classes: el.className || null,
        });
    });

    // 4. Important links
    document.querySelectorAll('a[href]').forEach(el => {
        if (el.offsetParent === null) return;
        const href = el.href || '';
        if (href.includes('activities') || href.includes('logout') || href.includes('login')) {
            result.links.push({
                text: (el.textContent || '').trim().substring(0, 80),
                href: href,
                selector: _bestSelector(el),
            });
        }
    });

    // 5. Popup containers
    document.querySelectorAll('.swal2-container, .modal, .popup, .overlay, [class*="popup"], [class*="modal"]').forEach(el => {
        result.popups.push({
            selector: _bestSelector(el),
            visible: el.offsetParent !== null || window.getComputedStyle(el).display !== 'none',
            classes: el.className || null,
        });
    });

    // 6. Prominent text blocks (headers, labels)
    document.querySelectorAll('h1, h2, h3, h4, .title, [class*="title"], [class*="header"], [class*="label"]').forEach(el => {
        if (el.offsetParent === null) return;
        const text = (el.textContent || '').trim();
        if (text.length > 0 && text.length < 200) {
            result.texts.push({
                tag: el.tagName.toLowerCase(),
                text: text.substring(0, 150),
                selector: _bestSelector(el),
            });
        }
    });

    // 7. Meta info
    result.meta = {
        title: document.title,
        url: window.location.href,
        bodyClasses: document.body.className || null,
    };

    function _bestSelector(el) {
        if (el.id) return '#' + el.id;
        if (el.className && typeof el.className === 'string') {
            const cls = el.className.trim().split(/\\s+/).filter(c => c.length > 0 && !c.startsWith('_'));
            if (cls.length > 0) {
                const sel = el.tagName.toLowerCase() + '.' + cls.join('.');
                if (document.querySelectorAll(sel).length === 1) return sel;
                if (cls.length > 0) return '.' + cls[0];
            }
        }
        return el.tagName.toLowerCase();
    }

    return result;
}
"""


def inspect_page(page, url, n, total, exe_id):
    """Dump selectors + screenshot จากหน้ากิจกรรม"""
    print(f"\n{'='*60}", flush=True)
    print(f"  ACTIVITY PAGE INSPECTOR", flush=True)
    print(f"  URL: {url}", flush=True)
    print(f"  Account: {exe_id}", flush=True)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"{'='*60}\n", flush=True)

    # 1. Navigate to activity
    status(n, total, f"Navigate to activity: {url[:60]}...", exe_id)
    safe_goto(page, url, n, total, exe_id)

    # 2. Check if login needed
    current_url = page.url.lower()
    if "passport.exe.in.th" in current_url or "accounts.exe.in.th" in current_url:
        status(n, total, "Login page detected — need credentials", exe_id)
        return None

    # 3. Bypass Cloudflare if needed
    bypass_cloudflare(page, n, total, exe_id, status)

    # 4. Wait for content to load
    page.wait_for_timeout(3000)
    wait_for_content(page, "body", n, total, exe_id, timeout_ms=15000, max_retries=1)
    page.wait_for_timeout(2000)

    # 5. Run inspector JS
    status(n, total, "Inspecting page elements...", exe_id)
    try:
        data = page.evaluate(_INSPECT_JS)
    except Exception as e:
        print(f"Error running inspector JS: {e}", flush=True)
        data = {}

    # 6. Screenshot
    ss_dir = PROJECT_ROOT / "screenshots" / "inspect"
    ss_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ss_path = ss_dir / f"inspect_{ts}.png"
    ss_full_path = ss_dir / f"inspect_{ts}_full.png"

    try:
        page.screenshot(path=str(ss_path))
        page.screenshot(path=str(ss_full_path), full_page=True)
        print(f"\n📸 Screenshot: {ss_path}", flush=True)
        print(f"📸 Full page:  {ss_full_path}", flush=True)
    except Exception as e:
        print(f"Screenshot error: {e}", flush=True)

    # 7. Also get raw outer HTML of key containers
    status(n, total, "Extracting page structure...", exe_id)
    html_snippet = ""
    try:
        html_snippet = page.evaluate("""
        () => {
            // Get the main content area (not the full page)
            const candidates = [
                document.querySelector('.main-event'),
                document.querySelector('.main-content'),
                document.querySelector('.content-wrapper'),
                document.querySelector('.container'),
                document.querySelector('main'),
                document.querySelector('#app'),
                document.querySelector('.app'),
            ];
            for (const el of candidates) {
                if (el) {
                    return el.outerHTML.substring(0, 8000);
                }
            }
            return document.body.innerHTML.substring(0, 8000);
        }
        """)
    except:
        pass

    # 8. Print results
    _print_report(data, html_snippet)

    # 9. Save JSON report
    report_path = ss_dir / f"inspect_{ts}.json"
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump({"data": data, "html_snippet": html_snippet[:5000]}, f, ensure_ascii=False, indent=2)
        print(f"\n📋 Report: {report_path}", flush=True)
    except:
        pass

    return data


def _print_report(data, html_snippet=""):
    """Print formatted inspection report"""
    if not data:
        print("❌ No data collected", flush=True)
        return

    meta = data.get("meta", {})
    print(f"\n📄 Page: {meta.get('title', 'N/A')}", flush=True)
    print(f"🔗 URL: {meta.get('url', 'N/A')}", flush=True)

    # Buttons
    buttons = data.get("buttons", [])
    print(f"\n🔘 BUTTONS ({len(buttons)}):", flush=True)
    print(f"{'─'*50}", flush=True)
    for b in buttons:
        disabled = " [DISABLED]" if b.get("disabled") else ""
        text = b.get("text", "").replace("\n", " ")[:60]
        print(f"  {b['selector']:<40} | {text}{disabled}", flush=True)

    # Points/Scores
    points = data.get("points", [])
    print(f"\n💰 POINTS/SCORES ({len(points)}):", flush=True)
    print(f"{'─'*50}", flush=True)
    for p in points:
        digit_mark = " ← HAS DIGITS" if p.get("hasDigits") else ""
        text = p.get("text", "").replace("\n", " ")[:60]
        print(f"  {p['selector']:<40} | {text}{digit_mark}", flush=True)

    # Login/Profile
    forms = data.get("forms", [])
    if forms:
        print(f"\n👤 LOGIN/PROFILE ({len(forms)}):", flush=True)
        print(f"{'─'*50}", flush=True)
        for f in forms:
            text = f.get("text", "").replace("\n", " ")[:60]
            print(f"  {f['selector']:<40} | {text}", flush=True)

    # Texts
    texts = data.get("texts", [])
    if texts:
        print(f"\n📝 TITLES/HEADERS ({len(texts)}):", flush=True)
        print(f"{'─'*50}", flush=True)
        for t in texts:
            text = t.get("text", "").replace("\n", " ")[:80]
            print(f"  {t['selector']:<40} | {text}", flush=True)

    # Links
    links = data.get("links", [])
    if links:
        print(f"\n🔗 ACTIVITY LINKS ({len(links)}):", flush=True)
        print(f"{'─'*50}", flush=True)
        for l in links:
            text = l.get("text", "").replace("\n", " ")[:40]
            print(f"  {text:<40} | {l.get('href', '')[:80]}", flush=True)

    # Popups
    popups = data.get("popups", [])
    if popups:
        print(f"\n⚡ POPUP CONTAINERS ({len(popups)}):", flush=True)
        print(f"{'─'*50}", flush=True)
        for p in popups:
            vis = "VISIBLE" if p.get("visible") else "hidden"
            print(f"  {p['selector']:<40} | {vis}", flush=True)

    # HTML snippet preview
    if html_snippet:
        print(f"\n📦 HTML SNIPPET (first 2000 chars):", flush=True)
        print(f"{'─'*50}", flush=True)
        print(html_snippet[:2000], flush=True)

    print(f"\n{'='*60}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Inspect activity page — dump selectors + screenshot")
    parser.add_argument("--url", required=True, help="Activity page URL")
    parser.add_argument("--file", type=Path, default=Path("IDGE.txt"), help="Accounts file (default: IDGE.txt)")
    parser.add_argument("--headless", action="store_true", help="Run headless")
    parser.add_argument("--login-url", default=LOGIN_URL_DEFAULT, help="Login page URL")
    parser.add_argument("--browser", default="chrome", choices=["chrome", "msedge", "chromium"])
    args = parser.parse_args()

    # Load first account
    if not args.file.exists():
        print(f"Error: {args.file} not found", file=sys.stderr)
        return 1

    accounts = load_accounts(args.file)
    if not accounts:
        print("Error: No accounts found", file=sys.stderr)
        return 1

    exe_id, password = accounts[0]
    print(f"Using account: {exe_id}", flush=True)

    with sync_playwright() as p:
        # Find browser
        browser_exe = None
        if args.browser == "chrome":
            for path in [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                str(Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe"),
            ]:
                if Path(path).exists():
                    browser_exe = path
                    break

        user_data_dir = str(PROJECT_ROOT / ".chrome_profile")

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--window-size=1920,1080",
            "--no-first-run",
            "--disable-features=PasswordCheck,PasswordLeakDetection",
            "--disable-translate",
            "--disable-infobars",
            "--disable-notifications",
        ]

        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            executable_path=browser_exe,
            channel="chrome" if not browser_exe else None,
            headless=args.headless,
            slow_mo=50,
            args=launch_args,
            ignore_default_args=["--enable-automation"],
            viewport={"width": 1920, "height": 1080},
            user_agent=USER_AGENT,
            locale="th-TH",
            timezone_id="Asia/Bangkok",
        )

        try:
            page = context.new_page()
            hide_automation(page)

            # Navigate to activity → may redirect to login
            status(1, 1, f"Going to {args.url[:60]}...", exe_id)
            safe_goto(page, args.url, 1, 1, exe_id)
            page.wait_for_timeout(2000)

            # Check if login needed
            current_url = page.url.lower()
            if "passport.exe.in.th" in current_url or "accounts.exe.in.th" in current_url:
                status(1, 1, "Login required — logging in...", exe_id)
                bypass_cloudflare(page, 1, 1, exe_id, status)
                human_delay(0.5, 1.0)

                from core.login_handlers import handle_login_any, check_login_error_any
                handle_login_any(page, exe_id, password, 1, 1, use_agent=True, human_type=False)

                err = check_login_error_any(page)
                if err:
                    print(f"❌ Login failed: {err}", flush=True)
                    page.close()
                    context.close()
                    return 1

                page.wait_for_timeout(3000)

                # If still on login page, navigate to activity again
                if "passport.exe.in.th" in page.url or "accounts.exe.in.th" in page.url:
                    safe_goto(page, args.url, 1, 1, exe_id)
                    page.wait_for_timeout(3000)

            # Now inspect
            inspect_page(page, args.url, 1, 1, exe_id)

            page.close()
        finally:
            context.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
