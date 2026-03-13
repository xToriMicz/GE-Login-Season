# -*- coding: utf-8 -*-
"""
ตรวจจับสถานะ slot Daily Login — รับแล้ว vs รับได้ vs ยังรับไม่ได้.
  - รับแล้ว = มี "รับไอเทมแล้ว" หรือ "ได้รับแล้ว" + checkmark → ไม่คลิก
  - รับได้ = สีเข้ม/สด (แถบหรือพื้นหลังเข้มพอ — green หรือ gold/brown ที่ไม่จาง)
  - ยังรับไม่ได้ = สีอ่อนกว่า (ไม่เข้มพอ) → ไม่คลิก
กิจกรรม Redeem: รูปที่รับได้สีเข้ม รูปที่ยังรับไม่ได้สีไม่เข้มเท่า — ใช้เงื่อนไข "เข้มพอ" กรอง
"""

# ข้อความที่แสดงเมื่อรับแล้ว — ตรงกับ state_received.png (รูปที่ 1) ถ้า slot มีข้อความนี้ = ไม่คลิก
# รองรับทั้ง "รับไอเทมแล้ว" (Daily Login ปกติ) และ "ได้รับแล้ว" (Daily Login Shop / Redeem)
TEXT_RECEIVED = "รับไอเทมแล้ว"
TEXTS_RECEIVED = ("รับไอเทมแล้ว", "ได้รับแล้ว")

# JS ตรวจว่า element หรือ ancestor มีพื้นหลังสี claimable: เขียว หรือทอง/น้ำตาลที่เข้มพอ (สีสด — รับได้).
# รูปที่รับได้ = สีเข้ม/สด; รูปที่ยังรับไม่ได้ = สีอ่อนกว่า → ต้องเช็คให้แถบ/พื้นหลัง "เข้มพอ" เท่านั้นถึงนับว่า claimable
IS_GREEN_BAR_JS = """
el => {
    if (!el) return false;
    function parseRgb(bg) {
        if (!bg) return null;
        const m = bg.match(/rgb\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*\\)/);
        if (m) return [parseInt(m[1],10), parseInt(m[2],10), parseInt(m[3],10)];
        const n = bg.match(/rgba?\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)/);
        if (n) return [+n[1], +n[2], +n[3]];
        return null;
    }
    function looksGreen(rgb) {
        if (!rgb) return false;
        const [r,g,b] = rgb;
        // ปรับให้ครอบคลุมเขียวหลายโทนขึ้น (เขียวมะนาว, เขียวขี้ม้า, เขียวสด)
        return g >= 70 && g > r && g > b;
    }
    function looksGold(rgb, requireDark) {
        if (!rgb) return false;
        const [r,g,b] = rgb;
        const sum = r + g + b;
        if (r >= 100 && g >= 80 && b < 140 && Math.abs(r - g) < 100) {
            return !requireDark || sum < 520;
        }
        if (r >= 70 && g >= 60 && b >= 25 && r <= 200 && g <= 180 && sum < 520) {
            return true;
        }
        return false;
    }
    function hasReadyClass(e) {
        if (!e) return false;
        if (e.classList && e.classList.contains('items-ready')) return true;
        return false;
    }

    let e = el;
    let depth = 0;
    while (e && depth < 15) {
        try {
            if (hasReadyClass(e)) return true;
            const s = window.getComputedStyle(e);
            const rgb = parseRgb(s && s.backgroundColor);
            if (rgb && looksGreen(rgb)) return true;
            if (rgb && looksGold(rgb, true)) return true;
            
            // เช็คลูกๆ ด้วยเผื่อปลาติด (เฉพาะชั้นแรก)
            if (depth === 0) {
                const children = e.querySelectorAll ? e.querySelectorAll('*') : [];
                for (let i = 0; i < children.length && i < 20; i++) {
                    if (hasReadyClass(children[i])) return true;
                }
            }
        } catch (_) {}
        e = e.parentElement;
        depth++;
    }
    return false;
}
"""

# โหมดผ่อนสำหรับกิจกรรม Redeem — รับแถบทอง/น้ำตาลได้แม้สีไม่เข้มมาก (ลดโอกาสไม่กดคลิก)
IS_CLAIMABLE_REDEEM_JS = """
el => {
    if (!el) return false;
    function parseRgb(bg) {
        if (!bg) return null;
        const m = bg.match(/rgb\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*\\)/);
        if (m) return [parseInt(m[1],10), parseInt(m[2],10), parseInt(m[3],10)];
        const n = bg.match(/rgba?\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)/);
        if (n) return [+n[1], +n[2], +n[3]];
        return null;
    }
    function looksGreen(rgb) {
        if (!rgb) return false;
        const [r,g,b] = rgb;
        return g >= 80 && g > r && g > b;
    }
    function looksWarm(rgb) {
        if (!rgb) return false;
        const [r,g,b] = rgb;
        if (r >= 70 && g >= 60 && b <= 180 && (r + g + b) < 620) return true;
        if (r >= 80 && g >= 70 && b >= 30 && b < 150 && (r + g + b) < 550) return true;
        return false;
    }
    let e = el;
    let depth = 0;
    while (e && depth < 15) {
        try {
            const s = window.getComputedStyle(e);
            const rgb = parseRgb(s && s.backgroundColor);
            if (rgb && looksGreen(rgb)) return true;
            if (rgb && looksWarm(rgb)) return true;
        } catch (_) {}
        e = e.parentElement;
        depth++;
    }
    return false;
}
"""

# โหมด Redeem — จับเฉพาะ gradient รับได้เท่านั้น (สีตรงที่ให้มา) ไม่ใช้เงื่อนไขกว้าง เพื่อไม่ให้ Day 2,3,4,5 สีจางติด
# สีจริงจากหน้า: linear-gradient(180deg, rgba(75, 32, 10, 1) 5%, rgba(149, 74, 28, 1) 95%)
IS_CLAIMABLE_REDEEM_VIBRANT_JS = """
el => {
    if (!el) return false;
    function parseRgb(bg) {
        if (!bg) return null;
        const m = bg.match(/rgb\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*\\)/);
        if (m) return [parseInt(m[1],10), parseInt(m[2],10), parseInt(m[3],10)];
        const n = bg.match(/rgba?\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)/);
        if (n) return [+n[1], +n[2], +n[3]];
        return null;
    }
    function parseGradientRgba(img) {
        if (!img || typeof img !== 'string' || img.indexOf('linear-gradient') === -1) return [];
        const out = [];
        const re = /rgba?\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)/g;
        let m;
        while ((m = re.exec(img)) !== null) { out.push([+m[1], +m[2], +m[3]]); }
        return out;
    }
    var CLAIM_RGB2 = [149, 74, 28];
    var T = 35; // เพิ่ม tolerance ให้กว้างขึ้น
    function isClaimableColor(rgb) {
        if (!rgb || rgb.length < 3) return false;
        var r = rgb[0], g = rgb[1], b = rgb[2];
        
        // 1. ตรวจสอบสีทอง/ส้ม/น้ำตาลของปุ่มหรือพื้นหลัง (Claimable)
        // สีจากหน้าจอกิจกรรมที่เป็น Day รับได้มักจะมีสีสดกว่า
        const isVibrant = (r > 100 && g > 50 && r > b);
        const isWarm = (r >= 70 && g >= 50 && b <= 50);
        
        if (isVibrant || isWarm) return true;
        
        // 2. ตรวจสอบสีหัวข้อ (Header) ของช่องที่พร้อมรับ (มักเป็นสีน้ำตาลเข้มจัด)
        if (r >= 35 && r <= 100 && g >= 15 && g <= 60 && b <= 35 && r > g) return true;

        return false;
    }
    function checkEl(e) {
        try {
            const s = window.getComputedStyle(e);
            
            // ถ้าโปร่งใสมาก (Opacity < 0.6) แสดงว่าเป็นช่องที่ยังไม่เปิดให้รับแน่นอน
            const opacity = parseFloat(s && s.opacity || "1");
            if (opacity < 0.7) return false;

            const bg = s && s.backgroundColor;
            const rgb = parseRgb(bg);
            if (rgb && isClaimableColor(rgb)) return true;
            
            const img = s && s.backgroundImage;
            const list = parseGradientRgba(img);
            for (let i = 0; i < list.length; i++) {
                if (isClaimableColor(list[i])) return true;
            }
        } catch (_) {}
        return false;
    }
    if (checkEl(el)) return true;
    const all = el.querySelectorAll ? el.querySelectorAll('*') : [];
    for (let i = 0; i < all.length && i < 60; i++) {
        if (checkEl(all[i])) return true;
    }
    return false;
}
"""

# JS ตรวจว่า slot นี้รับแล้วหรือไม่ — ดูข้อความใน container (เดินขึ้น ancestor สูงสุด 12 ระดับ)
# รองรับ: รับไอเทมแล้ว, ได้รับแล้ว, รับโบนัสแล้ว (Daily Login Shop หลังกดรับแล้วจะแสดงรับโบนัสแล้ว + พื้นเขียว)
IS_RECEIVED_JS = """
el => {
    if (!el) return false;
    // ตรวจสอบเฉพาะคำที่บ่งบอกว่ารับสำเร็จแล้วจริงๆ เท่านั้น
    const texts = ['รับไอเทมแล้ว', 'ได้รับแล้ว', 'รับไปแล้ว'];
    
    function hasReceivedText(e) {
        if (!e) return false;
        if (e.classList && e.classList.contains('items-successed')) return true;
        const t = (e.innerText || e.textContent || '').trim();
        for (const txt of texts) {
            if (t.indexOf(txt) >= 0) return true;
        }
        return false;
    }

    let current = el;
    for (let i = 0; i < 8 && current; i++) {
        if (hasReceivedText(current)) return true;
        if (i === 0) {
            const children = current.querySelectorAll ? current.querySelectorAll('*') : [];
            for (let j = 0; j < children.length && j < 50; j++) {
                if (hasReceivedText(children[j])) return true;
            }
        }
        current = current.parentElement;
    }
    return false;
}
"""


def is_slot_claimable(slot, permissive: bool = False) -> bool:
    """
    คืน True เฉพาะเมื่อ slot นี้เป็นสถานะ "รับวันนี้ได้".
    ถ้ารับแล้ว (มี รับไอเทมแล้ว/ได้รับแล้ว) = False เสมอ.
    permissive=True: ใช้กับกิจกรรม Redeem — รับแถบทอง/น้ำตาลได้แม้สีไม่เข้มมาก (ลดโอกาสไม่กดคลิก).
    """
    try:
        if slot.evaluate(IS_RECEIVED_JS):
            return False
        js = IS_CLAIMABLE_REDEEM_JS if permissive else IS_GREEN_BAR_JS
        return bool(slot.evaluate(js))
    except Exception:
        return False


def get_slot_state(slot, permissive: bool = False, use_vibrant: bool = False) -> str:
    """
    คืนสถานะ slot สำหรับ debug: "received" | "claimable" | "unknown".
    permissive=True ใช้ชุดตรวจแบบ Redeem.
    use_vibrant=True (ใช้กับ permissive) = จับสีทองเหลืองสด + ตรวจทั้ง slot และ descendants.
    """
    try:
        if slot.evaluate(IS_RECEIVED_JS):
            return "received"
        if permissive and use_vibrant:
            js = IS_CLAIMABLE_REDEEM_VIBRANT_JS
        else:
            js = IS_CLAIMABLE_REDEEM_JS if permissive else IS_GREEN_BAR_JS
        if slot.evaluate(js):
            return "claimable"
        return "unknown"
    except Exception:
        return "unknown"
