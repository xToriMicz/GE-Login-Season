# -*- coding: utf-8 -*-
"""
Notification system — Discord webhook (expandable to LINE, Telegram, etc.)
"""

import json
import urllib.request
from datetime import datetime


def send_discord(webhook_url: str, title: str, description: str,
                 color: int = 0x22c55e, fields: list = None) -> bool:
    """
    Send Discord embed via webhook.
    Returns True if sent successfully.
    """
    if not webhook_url or not webhook_url.startswith("https://discord.com/api/webhooks/"):
        return False

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if fields:
        embed["fields"] = fields

    payload = json.dumps({"embeds": [embed]}).encode("utf-8")

    try:
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "GE-Login-Bot/2.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 204)
    except Exception:
        return False


def notify_run_complete(webhook_url: str, activity: str, total: int,
                        success: int, fail: int, duration: str,
                        failed_ids: list = None, bad_cred_ids: list = None) -> bool:
    """Send run completion notification to Discord."""
    rate = round(success / total * 100, 1) if total > 0 else 0
    color = 0x22c55e if fail == 0 else 0xf59e0b if rate >= 80 else 0xef4444

    fields = [
        {"name": "Total", "value": str(total), "inline": True},
        {"name": "Success", "value": str(success), "inline": True},
        {"name": "Failed", "value": str(fail), "inline": True},
        {"name": "Success Rate", "value": f"{rate}%", "inline": True},
        {"name": "Duration", "value": duration, "inline": True},
    ]

    # Add failed IDs (max 10, then "...and N more")
    if failed_ids:
        MAX_SHOW = 10
        shown = failed_ids[:MAX_SHOW]
        text = ", ".join(shown)
        if len(failed_ids) > MAX_SHOW:
            text += f"\n...and {len(failed_ids) - MAX_SHOW} more"
        fields.append({"name": "Failed IDs (server/network)", "value": text, "inline": False})

    # Add bad credential IDs
    if bad_cred_ids:
        MAX_SHOW = 10
        shown = bad_cred_ids[:MAX_SHOW]
        text = ", ".join(shown)
        if len(bad_cred_ids) > MAX_SHOW:
            text += f"\n...and {len(bad_cred_ids) - MAX_SHOW} more"
        fields.append({"name": "Bad Credentials (fix/remove)", "value": text, "inline": False})

    return send_discord(
        webhook_url,
        title=f"GE Login Bot — {activity}",
        description=f"{'All Success!' if fail == 0 else f'{fail} failed'}",
        color=color,
        fields=fields,
    )
