# Changelog

## [1.3.0] - 2026-02-13

### 💕 Valentine's Feb 2026 — Heart Arrow
- **New Activity:** Added `ge-valentine-feb-2026` (Heart Arrow) — สะสม Love Energy และ Heart Arrow
- **Valentine Tab:** เพิ่มแท็บ "Valentine 2026" ใน UI พร้อม Activity URL override
- **Heart Arrow Counter:** อ่านค่า Heart Arrow จากหน้ากิจกรรม แสดงผลใน log และ report
- **Report Column:** เพิ่มคอลัมน์ 🏹 Heart Arrow ใน HTML/CSV report

### 🐛 Fixes & Improvements
- **Cloudflare False Positive:** แก้ `bypass_cloudflare` ตรวจจับผิด — เว็บที่ใช้ Cloudflare CDN จะไม่ถูกจับเป็น Challenge page อีกต่อไป
- **URL Redirect Fix:** หลัง Login ระบบอาจ redirect ไปหน้ากิจกรรมอื่น (เช่น Daily Login) — เพิ่ม Step 0 ตรวจสอบ URL และนำทางกลับหน้า Valentine อัตโนมัติ
- **Safe Reload:** ปรับ `_safe_reload` ให้ใช้ `safe_goto` แทน `page.reload` เมื่ออยู่ผิดหน้า

### 🗑️ Removed
- **New Year 2026:** ถอดออกจาก registry (ไฟล์ยังอยู่ใน disk เพื่อเป็น reference)

## [1.2.0] - 2026-02-08

### ✨ New Features
- **Browser Selection:** Added option to choose between Chrome, Microsoft Edge, and Chromium.
- **Setup Browser Mode:** New feature to manually configure browser settings (e.g., disable password manager) before running automation.
- **Keep Browser Settings:** Transform checkbox to preserve user's manual configuration in the sandbox profile, skipping re-cloning.
- **Maintenance System:** Added junk file management to the Activities tab (Log/Preview cleanup, 7-day old file/folder removal).
- **Real-time Preview:** Enhanced preview tab with intermediate captures (after filling credentials) to show account names.
- **Auto-Retry:** Configurable retry attempts (0-3) for failed login/activity flows.

### 🗑️ Removed
- **Item Code Tab:** Removed the tab and related logic as the "Item Code" activity has ended.
- **Firefox Support:** Removed Firefox from browser options due to compatibility and environment issues.
- **Overwrite URL:** Removed redundant "Overwrite URL" field from the main Activities tab (each activity tab now handles its own URL override).

### 🐛 Fixes & Improvements
- **Chromium Handling:** Added informative warning when attempting to setup Chromium (manual setup not supported by Playwright's Chromium).
- **Profile Management:** Improved sandbox profile cloning logic to include essential data (extensions, preferences) while avoiding profile locks.
- **Code Cleanup:** Removed unused variables and functions related to legacy features.

## [1.1.0] - 2026-01-31

### ✨ New Features
- **UI Redesign:** Modernized UI with tabs and improved layout.
- **Daily Login & Shop:** Added support for GE Daily Login and Daily Shop activities.
- **New Year 2026:** Focused support for the "GE Leonardo New Year 2026" activity.

### 🛠️ Technical
- **Refactoring:** Split monolithic script into modular components (`core`, `ui`, `utils`, `activities`).
- **Playwright Integration:** Migrated to Playwright for better automation reliability.
