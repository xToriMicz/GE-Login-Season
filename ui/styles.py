# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

# ฟอนต์ที่รองรับภาษาไทยบน Windows
THAI_FONTS = ("Tahoma", "Leelawadee UI", "Microsoft Sans Serif", "Segoe UI")

# --- ธีมสี (Modern Dark Mode - High Contrast) ---
BG_MAIN = "#121212"
BG_CARD = "#1e1e1e"
BG_ENTRY = "#2d2d2d"
FG_MAIN = "#ffffff"
FG_DIM = "#b0b0b0"
FG_ACCENT = "#58a6ff"
FG_SUCCESS = "#4caf50"
FG_ERROR = "#ff5252"

def setup_thai_font(root):
    """ตั้งฟอนต์ให้ Tk/ttk แสดงภาษาไทยได้"""
    font_tuple = None
    for name in THAI_FONTS:
        try:
            font_tuple = (name, 9)
            root.option_add("*Font", f"{name} 9")
            break
        except tk.TclError:
            continue
    return font_tuple or ("Tahoma", 9)

def apply_dark_theme(root):
    """ตั้งค่า Style ให้ตัวหนังสือชัดเจนและตัดกับพื้นหลัง"""
    s = ttk.Style()
    s.theme_use('clam')

    s.configure(".", 
        background=BG_MAIN, 
        foreground=FG_MAIN, 
        fieldbackground=BG_ENTRY,
        insertcolor="white",
        borderwidth=0
    )

    s.configure("TFrame", background=BG_MAIN)
    s.configure("Card.TFrame", background=BG_CARD)

    s.configure("TLabel", background=BG_MAIN, foreground=FG_MAIN, padding=2)
    s.configure("Card.TFrame.TLabel", background=BG_CARD, foreground=FG_MAIN)
    s.configure("Header.TLabel", font=(THAI_FONTS[0], 12, "bold"), foreground=FG_ACCENT)
    s.configure("Total.TLabel", font=(THAI_FONTS[0], 10, "bold"), foreground=FG_SUCCESS, background=BG_MAIN)
    s.configure("TLabelframe.Label", font=(THAI_FONTS[0], 9, "bold"), foreground=FG_DIM)

    s.configure("TEntry", fieldbackground=BG_ENTRY, foreground="white", insertcolor="white", borderwidth=1, bordercolor="#444444")
    
    s.configure("TButton", background="#333333", foreground="white", borderwidth=0, padding=6, font=(THAI_FONTS[0], 9, "bold"))
    s.map("TButton", background=[("active", "#444444"), ("disabled", "#222222")])
    
    s.configure("Run.TButton", background="#007acc", foreground="white") 
    s.map("Run.TButton", background=[("active", "#005a9e")])

    s.configure("Orange.TButton", background="#ff9800", foreground="white")
    s.map("Orange.TButton", background=[("active", "#f57c00")])

    s.configure("TNotebook", background=BG_MAIN, borderwidth=0)
    s.configure("TNotebook.Tab", background=BG_CARD, foreground=FG_DIM, padding=[15, 5], font=(THAI_FONTS[0], 9))
    s.map("TNotebook.Tab", background=[("selected", BG_MAIN)], foreground=[("selected", FG_ACCENT)])

    s.configure("Section.TLabel", font=(THAI_FONTS[0], 11, "bold"), foreground=FG_MAIN, background="#333333", padding=5)
    
    s.configure("TCheckbutton", background=BG_MAIN, foreground=FG_MAIN, font=(THAI_FONTS[1] if len(THAI_FONTS)>1 else THAI_FONTS[0], 10))
    s.map("TCheckbutton", 
        foreground=[("active", "white"), ("selected", FG_ACCENT)], 
        background=[("active", BG_MAIN)]
    )

    s.configure("TCombobox", 
        fieldbackground=BG_ENTRY, 
        background="#333333", 
        foreground="white", 
        arrowcolor="white",
        borderwidth=1,
        darkcolor=BG_ENTRY,
        lightcolor=BG_ENTRY
    )
    s.map("TCombobox",
        fieldbackground=[("readonly", BG_ENTRY), ("active", BG_ENTRY)],
        foreground=[("readonly", "white"), ("active", "white")]
    )
    
    root.option_add("*TCombobox*Listbox.background", BG_CARD)
    root.option_add("*TCombobox*Listbox.foreground", "white")
    root.option_add("*TCombobox*Listbox.selectBackground", FG_ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "white")

    s.configure("TProgressbar", thickness=12, background=FG_ACCENT, troughcolor="#222222")
    root.configure(background=BG_MAIN)
