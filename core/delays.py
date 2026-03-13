# -*- coding: utf-8 -*-
"""
Delay และ timeout (มิลลิวินาที) สำหรับกรณีหน้าเว็บโหลดช้า / มี error / หน้าอื่นที่ไม่ตรงตามที่คาด.
ปรับค่าที่นี่เพื่อให้เหมาะสมกับเครือข่ายและโหลดของเซิร์ฟเวอร์
"""

# การโหลดหน้า (goto) — เผื่อคนเข้าเยอะ/โหลดช้า
NAVIGATION_TIMEOUT_MS = 60_000  # 60 วินาที
PAGE_SETTLE_AFTER_GOTO_MS = 5_000  # รอให้หน้า settle หลัง goto
PAGE_SETTLE_AFTER_LOGIN_MS = 3_500  # หลังโหลดหน้า login (ก่อนกรอกฟอร์ม)

# หลังกดเข้าสู่ระบบ — เผื่อ redirect ช้า / SPA โหลดช้า
AFTER_LOGIN_CLICK_MS = 8_000
AFTER_SECOND_LOGIN_MS = 8_000  # หลังล็อกอินอีกชั้น (return_url)

# รอฟอร์ม login (รวม Cloudflare / หน้า error โหลดช้า)
LOGIN_FORM_WAIT_TIMEOUT_MS = 90_000  # รอฟอร์มโผล่ (รวมให้ user คลิก Verify)
LOGIN_INPUT_WAIT_TIMEOUT_MS = 25_000  # รอ input ใน _do_login_form (หน้า login อีกชั้น)

# ไปหน้ากิจกรรม
ACTIVITY_GOTO_SETTLE_MS = 5_000  # หลัง goto หน้ากิจกรรม

# Logout — เผื่อปุ่มโหลดช้า
LOGOUT_CLICK_TIMEOUT_MS = 8_000
LOGOUT_FALLBACK_TIMEOUT_MS = 5_000

# --- กิจกรรม Daily Login ---
DAILY_LOGIN_INITIAL_MS = 2_500  # รอให้หน้ากิจกรรมโหลดเต็มก่อนหา slot
DAILY_LOGIN_AFTER_SCROLL_MS = 600  # หลัง scroll slot เข้ามาในหน้าจอ
DAILY_LOGIN_AFTER_CLICK_SLOT_MS = 1_500  # รอ popup โผล่ (คนเข้าเยอะอาจช้า)
DAILY_LOGIN_POPUP_CLOSE_WAIT_MS = 10_000  # รอปุ่ม CLOSE ใน popup (timeout)
DAILY_LOGIN_AFTER_CLOSE_MS = 1_500  # หลังกด CLOSE รอให้ DOM อัปเดต (รับไอเทมแล้ว) ก่อนหาสล็อตถัดไป — ลดกดซ้ำ
