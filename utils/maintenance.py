# -*- coding: utf-8 -*-
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def get_folder_size_mb(path: Path) -> float:
    """คำนวณขนาดโฟลเดอร์เป็น MB"""
    if not path.exists():
        return 0.0
    total = 0
    for f in path.glob('**/*'):
        if f.is_file():
            total += f.stat().st_size
    return round(total / (1024 * 1024), 2)

def get_junk_stats():
    """สรุปสถานะไฟล์ขยะ"""
    logs_file = PROJECT_ROOT / "logs.txt"
    preview_dir = PROJECT_ROOT / ".preview"
    screenshots_dir = PROJECT_ROOT / "screenshots"
    reports_dir = PROJECT_ROOT / "reports"
    
    stats = {
        "logs_size": round(logs_file.stat().st_size / (1024 * 1024), 2) if logs_file.exists() else 0.0,
        "preview_size": get_folder_size_mb(preview_dir),
        "screenshots_size": get_folder_size_mb(screenshots_dir),
        "reports_size": get_folder_size_mb(reports_dir),
    }
    stats["total_size"] = round(sum(stats.values()), 2)
    return stats

def clean_previews():
    """ลบไฟล์ในโฟลเดอร์ .preview"""
    path = PROJECT_ROOT / ".preview"
    if path.exists():
        shutil.rmtree(path)
        path.mkdir()
    return True

def clean_logs():
    """ล้างไฟล์ log (truncate เป็นว่างเปล่า)"""
    path = PROJECT_ROOT / "logs.txt"
    if path.exists():
        with open(path, 'w', encoding='utf-8') as f:
            f.write("")
    return True

def clean_old_files(days=7):
    """ลบ screenshots และ reports ที่เก่ากว่าวันที่กำหนด"""
    cutoff = datetime.now() - timedelta(days=days)
    count = 0
    
    for folder in ["screenshots", "reports"]:
        path = PROJECT_ROOT / folder
        if not path.exists(): continue
        
        for item in path.glob('**/*'):
            if item.is_file():
                mtime = datetime.fromtimestamp(item.stat().st_mtime)
                if mtime < cutoff:
                    try:
                        item.unlink()
                        count += 1
                    except: pass
                    
    # ลบโฟลเดอร์ย่อยที่ว่างเปล่าแบบวนซ้ำ (Recursive) เพื่อความสะอาดที่สุด
    for folder in ["screenshots", "reports"]:
        root_path = PROJECT_ROOT / folder
        if not root_path.exists(): continue
        
        # เดินย้อนกลับจากล่างขึ้นบนเพื่อลบโฟลเดอร์ย่อยที่ว่าง
        for dirpath, dirnames, filenames in os.walk(root_path, topdown=False):
            if dirpath == str(root_path): continue # ไม่ลบโฟลเดอร์หลัก
            
            try:
                if not os.listdir(dirpath):
                    os.rmdir(dirpath)
                    count += 1
            except: pass
                
    return count
