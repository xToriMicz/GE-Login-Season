# -*- coding: utf-8 -*-
"""
โหมด agent — ค่าคงที่และฟังก์ชันให้เบราว์เซอร์/พฤติกรรมคล้ายคนใช้ (ลดการถูก Cloudflare บล็อก).
Single Responsibility: เรื่อง agent/stealth เท่านั้น
"""

import random
import time

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36"
)


def human_delay(min_sec: float = 0.2, max_sec: float = 0.6) -> None:
    """รอแบบสุ่ม เหมือนคนคิด/เลื่อนเมาส์"""
    time.sleep(random.uniform(min_sec, max_sec))


def hide_automation(page) -> None:
    """ฉีด JS เพื่อซ่อนร่องรอย Automation ระดับลึก (Deep Stealth)"""
    stealth_js = """
    // 1. Hide WebDriver & CDC
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    delete navigator.__proto__.webdriver;

    // 2. Mock Hardware Properties (ให้ดูเหมือนเครื่องจริง)
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

    // 3. Mock Chrome properties
    window.chrome = {
        runtime: {},
        app: { isInstalled: false, InstallState: { DISABLED: "disabled", INSTALLED: "installed", NOT_INSTALLED: "not_installed" } },
        loadTimes: () => {},
        csi: () => {}
    };

    // 4. Mock Languages & Plugins
    Object.defineProperty(navigator, 'languages', { get: () => ['th-TH', 'th', 'en-US', 'en'] });
    Object.defineProperty(navigator, 'plugins', { get: () => {
        const p = [
            { description: "Portable Document Format", filename: "internal-pdf-viewer", name: "Chrome PDF Viewer" },
            { description: "", filename: "internal-pdf-viewer", name: "Chromium PDF Viewer" }
        ];
        return { length: p.length, item: (i) => p[i], namedItem: (n) => p.find(x => x.name === n), ...p };
    }});

    // 5. Mock WebGL Vendors (Intel Iris Xe)
    const getParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel(R) Iris(R) Xe Graphics';
        return getParam.apply(this, arguments);
    };

    // 6. Mock Permissions
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (p) => (
        p.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : originalQuery(p)
    );

    // 7. Mock Screen Properties
    Object.defineProperty(window, 'screen', { get: () => ({ width: 1920, height: 1080, availWidth: 1920, availHeight: 1040, colorDepth: 24, pixelDepth: 24 }) });
    """
    try:
        page.add_init_script(stealth_js)
    except:
        pass


def bypass_cloudflare(page, n: int, total: int, exe_id: str, status_fn) -> bool:
    """พยายาม Bypass Cloudflare Turnstile โดยเน้นการตรวจจับสภาวะหน้าจอ"""
    try:
        # 1. เช็คว่าอยู่หน้า Cloudflare Challenge จริงไหม
        #    หมายเหตุ: คำว่า "cloudflare" เฉยๆ กว้างเกินไป เพราะเว็บทั่วไปใช้ Cloudflare CDN
        #    ต้องเช็คจาก Challenge-specific indicators เท่านั้น
        challenge_indicators = [
            "verify you are human", "ยืนยันว่าคุณเป็นมนุษย์", "ตรวจดูว่าเป็นมนุษย์", "ยืนยันว่าเป็นมนุษย์",
            "กำลังตรวจสอบว่าคุณคือมนุษย์", "กำลังตรวจสอบ...", "ต้องตรวจสอบความปลอดภัยการเชื่อมต่อ",
            "challenge-running", "challenge-platform", "challenge-form"
        ]
        page_content = page.content().lower()
        is_cf = any(ind.lower() in page_content for ind in challenge_indicators) or \
                page.locator('iframe[src*="challenges.cloudflare.com"]').count() > 0 or \
                page.locator('iframe[src*="turnstile"]').count() > 0
        
        # ถ้าหน้ามี content จริงแล้ว (เช่น .id-name, .love-energy) ไม่ใช่ Cloudflare
        if is_cf:
            has_real_content = (
                page.locator('.id-name, .love-energy, .btn-refresh, input[name="password"]').first.count() > 0
            )
            if has_real_content:
                is_cf = False

        if not is_cf:
            return False

        status_fn(n, total, "[Agent] Cloudflare detected. Waiting for challenge...", exe_id)
        page.wait_for_timeout(6000)

        # 2. ลองคลิก checkbox ในหน้าหลักก่อน (บางหน้า checkbox อยู่นอก iframe)
        for label in ["ยืนยันว่าคุณเป็นมนุษย์", "Confirm you are human", "Verify you are human"]:
            try:
                cb = page.get_by_text(label, exact=False).first
                if cb.count() > 0 and cb.is_visible(timeout=2000):
                    status_fn(n, total, f"[Agent] Clicking label: {label[:20]}...", exe_id)
                    cb.click(timeout=5000)
                    page.wait_for_timeout(4000)
                    break
            except Exception:
                pass
        try:
            chk = page.get_by_role("checkbox").first
            if chk.count() > 0 and chk.is_visible(timeout=1000):
                status_fn(n, total, "[Agent] Clicking checkbox (main page).", exe_id)
                chk.click(timeout=5000)
                page.wait_for_timeout(4000)
        except Exception:
            pass

        # 3. ลองคลิกใน Iframe (Turnstile / Cloudflare challenge)
        iframe_selectors = [
            'iframe[title*="Cloudflare"]', 'iframe[src*="cloudflare"]',
            'iframe[src*="turnstile"]', 'iframe[title*="challenge"]', 'iframe[title*="Widget"]'
        ]
        for iframe_sel in iframe_selectors:
            try:
                if page.locator(iframe_sel).count() == 0:
                    continue
                cf_iframe = page.frame_locator(iframe_sel).first
                if cf_iframe.locator('body').count() > 0:
                    for sel in [
                        'input[type="checkbox"]',
                        '[role="checkbox"]',
                        '.ctp-checkbox-label',
                        '#challenge-stage',
                    ]:
                        try:
                            target = cf_iframe.locator(sel).first
                            if target.count() > 0 and target.is_visible(timeout=2000):
                                status_fn(n, total, "[Agent] Clicking checkbox in iframe.", exe_id)
                                target.click(timeout=5000)
                                page.wait_for_timeout(4000)
                                break
                        except Exception:
                            continue
                    try:
                        txt_btn = cf_iframe.get_by_text("ยืนยัน", exact=False).first
                        if txt_btn.count() > 0 and txt_btn.is_visible(timeout=2000):
                            status_fn(n, total, "[Agent] Clicking 'ยืนยัน' in iframe.", exe_id)
                            txt_btn.click(timeout=5000)
                            page.wait_for_timeout(4000)
                    except Exception:
                        pass
                    try:
                        txt_btn2 = cf_iframe.get_by_text("human", exact=False).first
                        if txt_btn2.count() > 0 and txt_btn2.is_visible(timeout=1000):
                            txt_btn2.click(timeout=5000)
                            page.wait_for_timeout(4000)
                    except Exception:
                        pass
                    try:
                        frame_el = page.locator(iframe_sel).first
                        box = frame_el.bounding_box()
                        if box:
                            # ลองคลิกที่ประมาณ 15% ของความกว้าง (จุดที่ Checkbox มักจะอยู่)
                            # และลองสุ่มตำแหน่งใกล้เคียง 3-4 จุด
                            for offset_x in [0.15, 0.20, 0.25]:
                                cx = box['x'] + box['width'] * offset_x + random.randint(-2, 2)
                                cy = box['y'] + box['height'] / 2 + random.randint(-2, 2)
                                page.mouse.move(cx, cy, steps=10)
                                page.wait_for_timeout(random.randint(200, 500))
                                page.mouse.click(cx, cy)
                                status_fn(n, total, f"[Agent] Attempting click at {int(offset_x*100)}% width...", exe_id)
                                page.wait_for_timeout(2000)
                                # เช็คเบื้องต้นว่าผ่านหรือยัง ถ้าตัว iframe หายไป หรือ content เปลี่ยน ให้หยุดคลิกต่อ
                                if page.locator(iframe_sel).count() == 0:
                                    break
                    except Exception:
                        pass
                    break
            except Exception:
                continue

        # 4. วนลูปตรวจสอบผลอย่างอดทน (รอสูงสุด 2 นาที — itemcode บางครั้งช้า)
        status_fn(n, total, "[Agent] Waiting for Cloudflare to pass... (คลิกในเบราว์เซอร์ช่วยได้)", exe_id)
        for _ in range(60):  # 60 * 2s = 120s
            # เช็คว่าไม่อยู่หน้า Cloudflare Challenge แล้ว
            page_content_now = page.content().lower()
            still_cf = any(
                t in page_content_now
                for t in ["กำลังตรวจสอบว่าคุณคือมนุษย์", "กำลังตรวจสอบ...", "ยืนยันว่าคุณเป็นมนุษย์", "challenge-running", "verify that you are human"]
            )
            if not still_cf and page.locator('iframe[src*="challenges.cloudflare.com"]').count() == 0:
                page.wait_for_timeout(2000)
                status_fn(n, total, "[Agent] Cloudflare cleared successfully.", exe_id)
                return True
            # เจอช่องกรอก หรือ content จริง = ผ่านแล้ว
            if page.locator('input[type="text"], .id-name, .love-energy, .btn-refresh').count() > 0:
                status_fn(n, total, "[Agent] Cloudflare cleared successfully.", exe_id)
                return True

            page.wait_for_timeout(2000)
            
        return False
    except Exception as e:
        status_fn(n, total, f"[Agent] Bypass warning: {str(e)[:40]}", exe_id)
        return False
