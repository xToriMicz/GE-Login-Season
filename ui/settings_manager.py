# -*- coding: utf-8 -*-
import json
import tkinter as tk
from tkinter import messagebox

class SettingsManager:
    def __init__(self, settings_file, window):
        self.settings_file = settings_file
        self.window = window

    def load(self):
        """โหลดการตั้งค่าจากไฟล์"""
        if not self.settings_file.exists():
            return
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # แมพข้อมูลกลับไปยังตัวแปรใน window
            self._set_var(self.window.var_file, data.get("file"))
            self._set_var(self.window.var_activity, data.get("activity"), choices=self.window.activity_ids)
            self._set_var(self.window.var_screenshots, data.get("screenshots_dir"))
            self._set_var(self.window.var_headless, data.get("headless"))
            self._set_var(self.window.var_no_agent, data.get("no_agent"))
            self._set_var(self.window.var_human_type, data.get("human_type"))
            self._set_var(self.window.var_no_screenshots, data.get("no_screenshots"))
            self._set_var(self.window.var_cookies_path, data.get("cookies_path"))
            self._set_var(self.window.var_keep_open, data.get("keep_open"))
            
            # Migration logic for browser_type
            browser_val = data.get("browser_type")
            if not browser_val:
                # Fallback to old use_chrome setting
                use_chrome = data.get("use_chrome", True)
                browser_val = "chrome" if use_chrome else "chromium"
            self._set_var(self.window.var_browser_type, browser_val)
            
            self._set_var(self.window.var_use_default_browser_cookies, data.get("use_default_browser_cookies"))
            self._set_var(self.window.var_chrome_user_data, data.get("chrome_user_data"))
            self._set_var(self.window.var_chrome_profile_name, data.get("chrome_profile_name"))
            self._set_var(self.window.var_daily_login_url, data.get("daily_login_url"))
            self._set_var(self.window.var_keep_browser_settings, data.get("keep_browser_settings"))
            self._set_var(self.window.var_max_retries, data.get("max_retries", 1))
            self._set_var(self.window.var_parallel, data.get("parallel", 1))
            self._set_var(self.window.var_start_index, data.get("start_index"))
            self._set_var(self.window.var_stop_index, data.get("stop_index"))
            self._set_var(self.window.var_cleanup_days, data.get("cleanup_days", 7))
            self._set_var(self.window.var_auto_close, data.get("auto_close"))
            self._set_var(self.window.var_proxy_file, data.get("proxy_file"))
            self._set_var(self.window.var_auto_daily, data.get("auto_daily"))
            self._set_var(self.window.var_schedule_hour, data.get("schedule_hour", 0))
            self._set_var(self.window.var_schedule_minute, data.get("schedule_minute", 30))
            self._set_var(self.window.var_discord_webhook, data.get("discord_webhook"))
            self._set_var(self.window.var_notify_discord, data.get("notify_discord"))
            self._set_var(self.window.var_retry_failed, data.get("retry_failed"))
            self._set_var(self.window.var_retry_delay_hours, data.get("retry_delay_hours", 1))
            self._set_var(self.window.var_retry_rounds, data.get("retry_rounds", 2))
            
            if "geometry" in data:
                try:
                    self.window.root.geometry(data["geometry"])
                except:
                    pass
        except (json.JSONDecodeError, OSError):
            pass

    def save(self, silent=False):
        """บันทึกการตั้งค่าปัจจุบัน"""
        try:
            data = {
                "file": self.window.var_file.get().strip(),
                "activity": self.window.var_activity.get().strip(),
                "screenshots_dir": self.window.var_screenshots.get().strip(),
                "cookies_path": self.window.var_cookies_path.get().strip(),
                "headless": self.window.var_headless.get(),
                "no_agent": self.window.var_no_agent.get(),
                "human_type": self.window.var_human_type.get(),
                "no_screenshots": self.window.var_no_screenshots.get(),
                "keep_open": self.window.var_keep_open.get(),
                "browser_type": self.window.var_browser_type.get(),
                "use_default_browser_cookies": self.window.var_use_default_browser_cookies.get(),
                "chrome_user_data": self.window.var_chrome_user_data.get().strip(),
                "chrome_profile_name": self.window.var_chrome_profile_name.get().strip(),
                "daily_login_url": self.window.var_daily_login_url.get().strip(),
                "keep_browser_settings": self.window.var_keep_browser_settings.get(),
                "max_retries": self.window.var_max_retries.get(),
                "parallel": self.window.var_parallel.get(),
                "start_index": self.window.var_start_index.get(),
                "stop_index": self.window.var_stop_index.get(),
                "cleanup_days": self.window.var_cleanup_days.get(),
                "auto_close": self.window.var_auto_close.get(),
                "proxy_file": self.window.var_proxy_file.get().strip(),
                "auto_daily": self.window.var_auto_daily.get(),
                "schedule_hour": self.window.var_schedule_hour.get(),
                "schedule_minute": self.window.var_schedule_minute.get(),
                "discord_webhook": self.window.var_discord_webhook.get().strip(),
                "notify_discord": self.window.var_notify_discord.get(),
                "retry_failed": self.window.var_retry_failed.get(),
                "retry_delay_hours": self.window.var_retry_delay_hours.get(),
                "retry_rounds": self.window.var_retry_rounds.get(),
                "geometry": self.window.root.geometry()
            }
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            if not silent:
                messagebox.showinfo("บันทึกการตั้งค่า", "บันทึกการตั้งค่าเรียบร้อย", parent=self.window.root)
        except OSError as e:
            if not silent:
                messagebox.showerror("ผิดพลาด", f"บันทึกไม่ได้: {e}", parent=self.window.root)

    def _set_var(self, var, value, choices=None):
        if value is None:
            return
        if choices and value not in choices:
            return
            
        if isinstance(var, tk.BooleanVar):
            var.set(bool(value))
        elif isinstance(var, tk.IntVar):
            try: var.set(int(value))
            except (ValueError, TypeError): pass
        else:
            var.set(str(value))
