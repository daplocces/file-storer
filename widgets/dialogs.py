import tkinter as tk
from tkinter import ttk

from constants import COLORS


class _BaseDialog(tk.Toplevel):
    def __init__(self, parent, title, font):
        super().__init__(parent)
        self.result = None
        self.configure(bg=COLORS["bg_light"])
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())

    def _center(self):
        self.update_idletasks()
        parent = self.master
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = self.winfo_width(), self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def _cancel(self):
        self.result = None
        self.destroy()


class StringDialog(_BaseDialog):
    def __init__(self, parent, title, prompt, font, initial=""):
        super().__init__(parent, title, font)

        tk.Label(self, text=prompt, font=font, bg=COLORS["bg_light"],
                 fg=COLORS["text"]).pack(padx=20, pady=(20, 8), anchor="w")

        self.entry_var = tk.StringVar(value=initial)
        entry = tk.Entry(self, textvariable=self.entry_var, font=font,
                          bg=COLORS["bg"], fg=COLORS["text"], insertbackground=COLORS["text"],
                          relief="flat", highlightthickness=1,
                          highlightbackground=COLORS["bar_bg"], highlightcolor=COLORS["accent"])
        entry.pack(fill="x", padx=20, pady=(0, 16), ipady=6)
        entry.focus_set()
        entry.select_range(0, "end")
        entry.icursor("end")
        entry.bind("<Return>", lambda e: self._ok())

        btn_row = tk.Frame(self, bg=COLORS["bg_light"])
        btn_row.pack(padx=20, pady=(0, 20), fill="x")
        ttk.Button(btn_row, text="OK", style="Accent.TButton", command=self._ok).pack(side="right")
        ttk.Button(btn_row, text="Cancel", command=self._cancel).pack(side="right", padx=(0, 8))

        self._center()
        self.wait_window(self)

    def _ok(self):
        self.result = self.entry_var.get().strip()
        self.destroy()


class ConfirmDialog(_BaseDialog):
    def __init__(self, parent, title, message, font, ok_label="Delete"):
        super().__init__(parent, title, font)

        tk.Label(self, text=message, font=font, bg=COLORS["bg_light"],
                 fg=COLORS["text"], wraplength=320, justify="left").pack(
            padx=20, pady=20, anchor="w")

        btn_row = tk.Frame(self, bg=COLORS["bg_light"])
        btn_row.pack(padx=20, pady=(0, 20), fill="x")
        ttk.Button(btn_row, text=ok_label, style="Accent.TButton", command=self._ok).pack(side="right")
        ttk.Button(btn_row, text="Cancel", command=self._cancel).pack(side="right", padx=(0, 8))

        self._center()
        self.wait_window(self)

    def _ok(self):
        self.result = True
        self.destroy()


class InfoDialog(_BaseDialog):
    def __init__(self, parent, title, message, font):
        super().__init__(parent, title, font)

        tk.Label(self, text=message, font=font, bg=COLORS["bg_light"],
                 fg=COLORS["text"], wraplength=360, justify="left").pack(
            padx=20, pady=20, anchor="w")

        btn_row = tk.Frame(self, bg=COLORS["bg_light"])
        btn_row.pack(padx=20, pady=(0, 20), fill="x")
        ttk.Button(btn_row, text="OK", style="Accent.TButton", command=self._cancel).pack(side="right")

        self._center()
        self.wait_window(self)


def ask_string(parent, title, prompt, font, initial=""):
    return StringDialog(parent, title, prompt, font, initial).result


def ask_confirm(parent, title, message, font, ok_label="Delete"):
    return bool(ConfirmDialog(parent, title, message, font, ok_label).result)


def show_info(parent, title, message, font):
    InfoDialog(parent, title, message, font)