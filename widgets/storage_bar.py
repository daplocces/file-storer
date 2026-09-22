import tkinter as tk

from constants import COLORS


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % rgb


def _lerp_color(c1, c2, t):
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return _rgb_to_hex((r, g, b))


class StorageBar(tk.Frame):
    def __init__(self, parent, label, font, height=16, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], **kwargs)
        self.label_text = label
        self.height = height
        self._fraction = 0.0
        self._phase = 0.0

        self.text_label = tk.Label(
            self, text=label, font=font, bg=COLORS["bg"],
            fg=COLORS["text_muted"], anchor="w"
        )
        self.text_label.pack(fill="x", padx=8, pady=(4, 2))

        self.canvas = tk.Canvas(self, height=height, bg=COLORS["bar_bg"], highlightthickness=0)
        self.canvas.pack(fill="x", padx=8, pady=(0, 6))
        self.canvas.bind("<Configure>", lambda e: self.redraw())

        self.after(50, self._animate)

    def update_usage(self, used_bytes, limit_bytes, used_text, limit_text):
        fraction = min(used_bytes / limit_bytes, 1.0) if limit_bytes else 0
        self._fraction = fraction
        self.text_label.config(text=f"{self.label_text}: {used_text} / {limit_text}")
        self.redraw()

    def _animate(self):
        if not self.winfo_exists():
            return
        self._phase = (self._phase + 0.01) % 1.0
        self.redraw()
        self.after(50, self._animate)

    def redraw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.height
        if w <= 1:
            return

        self.canvas.create_rectangle(0, 0, w, h, fill=COLORS["bar_bg"], outline="")

        fill_w = w * self._fraction
        if fill_w < 2:
            return

        step = 4
        base = COLORS["bar_fill"]
        highlight = COLORS["bar_highlight"]
        center = self._phase * fill_w
        band = max(fill_w * 0.18, 20)

        x = 0
        while x < fill_w:
            dist = abs(x - center)
            dist = min(dist, fill_w - dist)  # wrap around so the sweep loops smoothly
            t = max(0.0, 1 - dist / band)
            color = _lerp_color(base, highlight, t)
            self.canvas.create_rectangle(x, 0, min(x + step, fill_w), h, fill=color, outline="")
            x += step