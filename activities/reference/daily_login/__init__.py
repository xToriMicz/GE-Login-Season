# -*- coding: utf-8 -*-
"""
ดาต้าเบสรูปอ้างอิง Daily Login — เช็คแค่ 2 รูป: รับแล้ว vs รับได้ (แถบเขียว).
"""
from pathlib import Path

_REF_DIR = Path(__file__).resolve().parent

# รูปที่ 1 = รับแล้ว (checkmark + รับไอเทมแล้ว)
STATE_RECEIVED_IMAGE = _REF_DIR / "state_received.png"
# รูปที่ 2 = สามารถรับได้ (มีแถบเขียว)
STATE_CLAIMABLE_IMAGE = _REF_DIR / "state_claimable.png"

REFERENCE_IMAGES = {
    "received": STATE_RECEIVED_IMAGE,
    "claimable": STATE_CLAIMABLE_IMAGE,
}
