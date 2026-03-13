# System Architecture & Logic (ฉบับนักพัฒนา)

เอกสารฉบับนี้อธิบาย Logic การทำงานเชิงลึกของโปรแกรม เพื่อให้ผู้ที่มาพัฒนาต่อเข้าใจโครงสร้างและสามารถแก้ไขงานได้ง่ายขึ้น

---

## 🏗️ 1. โครงสร้างระบบ (System Components)

โปรแกรมนี้ถูกออกแบบมาตามหลัก **Single Responsibility** แยกหน้าที่กันชัดเจน:

- **`login.py` (The Orchestrator):** จุดเริ่มต้นของการรัน (Entry Point) ทำหน้าที่อ่าน Config, โหลดไอดี, และวนลูปสั่งรันทีละบัญชี
- **`core/login_flow.py` (The Brain):** หัวใจหลักที่ควบคุมลำดับขั้นตอนบนเบราว์เซอร์ (Browser Orchestration)
- **`core/login_handlers.py` (Strategy Pattern):** รวมฟังก์ชันคำสั่งสำหรับการล็อกอินในหน้าเว็บแบบต่างๆ (Modern vs Legacy)
- **`activities/` (The Muscle):** จัดเก็บ Logic ของแต่ละกิจกรรมแยกเป็นไฟล์ๆ ง่ายต่อการเพิ่มหรือลบกิจกรรม
- **`utils/` (The Helpers):** เครื่องมือสนับสนุน เช่น การโหลดบัญชี, การทำตัวเสมือนคน (Agent), และการสร้างรายงาน (Reporter)
- **`ui/` (The Face):** ส่วนติดต่อผู้ใช้ (Tkinter) ที่ไม่ได้ควบคุม Logic เบราว์เซอร์โดยตรง แต่ทำหน้าที่ สร้างชุดคำสั่งไปรันผ่าน `subprocess` พร้อมฟีเจอร์ **Setup Browser**

---

## 🔄 2. Logic การทำงาน (Dynamic Flow)

เราใช้ระบบ **Dynamic Flow (Activity-First)** เพื่อความรวดเร็วและยืดหยุ่นสูง:

1.  **Direct Goto:** บอทจะพยายามวิ่งไปที่หน้ากิจกรรม (`Activity URL`) ทันทีโดยไม่แวะหน้า Login ก่อน
2.  **Detection:** บอทจะตรวจสอบสถานะหน้าเว็บปัจจุบัน:
    *   ถ้าโดน Redirect ไปหน้าล็อกอิน (`passport` หรือ `accounts`) -> เข้าสู่กระบวนการ Login
    *   ถ้าเจอหน้าให้ยืนยันตัวตน (Cloudflare) -> เรียกใช้ `bypass_cloudflare`
3.  **Handler Selection:** เมื่อต้อง Login บอทจะเรียก `handle_login_any` ซึ่งจะเลือกชุดคำสั่งกรอกรหัสผ่านให้ตรงตามหน้าเว็บที่เห็น (Strategy Pattern)
4.  **Activity Execution:** เมื่อล็อกอินสำเร็จและอยู่ที่หน้ากิจกรรมแล้ว บอทจะเรียกฟังก์ชัน `run_after_goto` ของกิจกรรมนั้นๆ (ถ้ามี) เพื่อทำการคลิกรับของหรือเปิดแผ่นป้าย
5.  **Evidence & Wait:** ถ่ายรูป Screenshot เก็บเป็นหลักฐาน (แยก Folder ตามวันที่และกิจกรรม) และรอตามเวลา `wait_seconds` ที่กำหนด
6.  **Real-time Preview:** เรียกใช้ `save_preview` ในจังหวะสำคัญ (หลังกรอกรหัส, ก่อนรันกิจกรรม) เพื่อให้ผู้ใช้เห็นสถานะจริงบนหน้าจอ Preview Tab
7.  **Smart Logout:** กดปุ่ม Logout และคอยจัดการ **Popup Confirm** (เช่น ปุ่ม ตกลง/ยืนยัน/ปิด) ที่อาจโผล่มาหลังกด Logout เพื่อให้ Session จบลงอย่างสมบูรณ์

---

## 🌐 3. การจัดการ Browser & Profile (New!)

### 3.1 Browser Selection
รองรับการระบุ Browser ผ่าน argument `--browser`:
- **chrome** (Default): ค้นหา path ของ Chrome ที่ติดตั้งในเครื่อง (Program Files / AppData)
- **msedge**: ค้นหา path ของ Microsoft Edge
- **chromium**: ใช้ Chromium ที่มาพร้อมกับ Playwright

### 3.2 Profile Sandbox & Cloning
เพื่อป้องกันปัญหา **Profile Locked** เมื่อเปิด Chrome ทิ้งไว้ เราใช้เทคนิค **Sandbox Cloning**:
1.  **Clone:** เมื่อเริ่มรัน โปรแกรมจะ copy ไฟล์สำคัญจาก Profile จริง (Cookies, Preferences, Extensions, Local Storage) ไปยังโฟลเดอร์ `.chrome_sandbox`
2.  **Launch:** Playwright จะเปิด Browser โดยใช้ User Data Dir เป็น `.chrome_sandbox`
3.  **Result:** ได้ Session และ Extension ที่เหมือนเปิด Chrome ปกติ แต่ไม่ติด Lock และปลอดภัยกว่า

### 3.3 Setup Browser Mode
โหมดพิเศษสำหรับให้ User ตั้งค่า Profile (`.chrome_sandbox`) ได้เอง:
- เปิด Chrome ด้วย Profile Sandbox
- เปิดหน้า `chrome://settings/passwords` ทันทีเพื่อให้ User ปิด Password Manager
- เมื่อ User ตั้งค่าเสร็จและเลือก **Keep Browser Settings** โปรแกรมจะข้ามขั้นตอน Clone และใช้ Sandbox ที่ตั้งค่าไว้แล้วในการรันครั้งต่อไป

---

*   **Data Flow:** ข้อมูลผลลัพธ์จาก `login_flow.py` จะถูกส่งกลับมาที่ `login.py` เพื่อรวบรวมและสร้างรายงานผ่าน `utils/reporter.py` เมื่อรันเสร็จทุกบัญชี

---

## 🧹 4. ระบบ Maintenance & Cleanup

เพิ่มความสามารถในการจัดการไฟล์ขยะที่เกิดจากการทำงาน:
- **Junk Calculation:** คำนวณขนาดไฟล์แยกตามประเภท (Logs, Preview, Reports)
- **Log Truncation:** ลบประวัติในไฟล์ `logs.txt` โดยไม่ต้องลบไฟล์ทิ้ง
- **Preview Clear:** ลบรูปภาพชั่วคราวในโฟลเดอร์ `.preview`
- **Recursive Cleanup:** ลบไฟล์ Screenshot/Report ที่เก่ากว่าจำนวนวันที่กำหนด พร้อมลบโฟลเดอร์ย่อยที่ว่างเปล่าแบบวนซ้ำ (Recursive) เพื่อความสะอาดสูงสุด

---

## 🛠️ 4. คำแนะนำสำหรับผู้เข้าแก้ไขงาน (Developer Tips)

### การเพิ่มกิจกรรมใหม่:
1.  สร้างไฟล์ใหม่ใน `activities/` โดย Copy โครงสร้างจากไฟล์เดิม
2.  นิยาม `Activity` และกำหนด `run_after_goto` ถ้ากิจกรรมนั้นต้องมีการคลิกบนหน้าจอ
3.  ลงทะเบียนไฟล์ใหม่ใน `activities/__init__.py`

### การปรับจูนความเร็ว:
- แก้ไขค่าหน่วงเวลา (Delays) ได้ที่ `core/delays.py`
- การใช้ `--no-agent` จะช่วยให้รันเร็วขึ้นมาก แต่ต้องระวังเรื่องโดน Cloudflare ตรวจจับ

### การเพิ่มปุ่มบน UI:
- แก้ไขที่ `ui/main_window.py`
- โปรแกรมใช้ `subprocess` รัน `login.py` ดังนั้นหากต้องการเพิ่มออปชันใหม่ ต้องไปเพิ่ม Argument รองรับที่ `login.py` ด้วย

---

*เอกสารฉบับนี้ปรับแต่งล่าสุดเมื่อ: 2026-01-31*
