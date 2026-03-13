# -*- coding: utf-8 -*-
"""
โหลดรายการบัญชีจากไฟล์ (exe_id,password ต่อบรรทัด).
Single Responsibility: อ่านและ parse ไฟล์บัญชีเท่านั้น
"""

from pathlib import Path


def load_accounts(filepath: Path) -> list[tuple[str, str]]:
    """Load (exe_id, password) pairs from file. UTF-8, one per line; skip empty and # lines."""
    accounts = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",", 1)
            if len(parts) >= 2:
                accounts.append((parts[0].strip(), parts[1].strip()))
    return accounts
