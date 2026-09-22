import os
import re
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog

from tkinterdnd2 import TkinterDnD, DND_FILES, COPY

import storage
from constants import APP_TITLE, COLORS, WINDOW_WIDTH, WINDOW_HEIGHT
from fonts import load_app_font
from widgets.storage_bar import StorageBar
from widgets.dialogs import ask_string, ask_confirm, show_info

if getattr(sys, "frozen", False):
    ASSETS_DIR = os.path.join(sys._MEIPASS, "assets")
else:
    ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        icon_path = os.path.join(ASSETS_DIR, "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        font_family = load_app_font(ASSETS_DIR)
        self.font_normal = (font_family, 10, "bold")
        self.font_header = (font_family, 12, "bold")

        self._setup_style()

        self.meta = storage.load_meta()
        self.current_channel = None
        self._channel_names = []
        self.sort_var = tk.StringVar(value="date")
        self.sort_labels = {"alpha": "A–Z", "date": "Date Added", "size": "File Size"}
        self._file_drag = None
        self._undo_stack = []
        self._drag_tooltip = None
        self._hover_tooltip = None
        self._hover_row = None

        self._build_layout()
        self.bind_all("<Control-z>", lambda e: self.undo_last())
        self.bind_all("<F2>", self._handle_f2)
        self.refresh_channels()
        self.refresh_files()
        self.refresh_overall_bar()

    def _setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Sidebar.TFrame", background=COLORS["sidebar"])
        style.configure("TButton", background=COLORS["button_bg"], foreground=COLORS["text"],
                         font=self.font_normal, borderwidth=0, focusthickness=0, padding=6,
                         focuscolor=COLORS["button_bg"])
        style.map("TButton", background=[("active", COLORS["accent"])])
        style.configure("Accent.TButton", background=COLORS["accent"], foreground="white",
                         font=self.font_normal, borderwidth=0, focusthickness=0, padding=6,
                         focuscolor=COLORS["accent"])
        style.map("Accent.TButton", background=[("active", COLORS["accent_hover"])])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=self.font_normal)

        style.configure("Treeview", background=COLORS["bg_light"], fieldbackground=COLORS["bg_light"],
                         foreground=COLORS["text"], font=self.font_normal, rowheight=26,
                         borderwidth=0, relief="flat",
                         bordercolor=COLORS["bg_light"], lightcolor=COLORS["bg_light"],
                         darkcolor=COLORS["bg_light"])
        style.map("Treeview", background=[("selected", COLORS["accent"])], foreground=[("selected", "white")])
        style.configure("Treeview.Heading", background=COLORS["sidebar"], foreground=COLORS["text"],
                         font=self.font_normal, borderwidth=0, relief="flat")
        style.map("Treeview.Heading", background=[("active", COLORS["sidebar"])])
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    def _build_layout(self):
        self.overall_bar = StorageBar(self, "App Storage", self.font_normal)
        self.overall_bar.pack(side="top", fill="x")

        body = ttk.Frame(self)
        body.pack(side="top", fill="both", expand=True)

        left = ttk.Frame(body, style="Sidebar.TFrame", width=220)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        ttk.Label(left, text="Channels", font=self.font_header,
                  background=COLORS["sidebar"]).pack(pady=8, padx=10, anchor="w")

        self.channel_list = tk.Listbox(
            left, exportselection=False, bg=COLORS["sidebar"], fg=COLORS["text"],
            selectbackground=COLORS["accent"], font=self.font_normal,
            borderwidth=0, highlightthickness=0, activestyle="none"
        )
        self.channel_list.pack(fill="both", expand=True, padx=10)
        self.channel_list.bind("<<ListboxSelect>>", self.on_select_channel)
        self.channel_list.bind("<Button-1>", self._on_channel_click)
        self.channel_list.bind("<Button-3>", self._show_channel_context_menu)

        self.channel_hint = tk.Label(left, text="", font=self.font_normal, bg=COLORS["sidebar"],
                                      fg=COLORS["text_muted"], wraplength=190, justify="left")
        self.channel_hint.pack(padx=10, pady=(4, 0), anchor="w")

        btn_row_l = ttk.Frame(left, style="Sidebar.TFrame")
        btn_row_l.pack(fill="x", padx=10, pady=8)
        ttk.Button(btn_row_l, text="+ Channel", command=self.add_channel).pack(side="left", padx=2)
        ttk.Button(btn_row_l, text="Delete", command=self.delete_channel).pack(side="left", padx=2)

        right = ttk.Frame(body)
        right.pack(side="right", fill="both", expand=True)

        ttk.Label(right, text="Files", font=self.font_header).pack(pady=(8, 0), padx=10, anchor="w")

        self.channel_bar = StorageBar(right, "This Channel", self.font_normal)
        self.channel_bar.pack(fill="x")

        search_row = ttk.Frame(right)
        search_row.pack(fill="x", padx=10, pady=(4, 6))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_files())
        search_entry = tk.Entry(
            search_row, textvariable=self.search_var, font=self.font_normal,
            bg=COLORS["bg_light"], fg=COLORS["text"], insertbackground=COLORS["text"],
            relief="flat", highlightthickness=1,
            highlightbackground=COLORS["bar_bg"], highlightcolor=COLORS["accent"]
        )
        search_entry.pack(side="left", fill="x", expand=True, ipady=4)

        self.sort_btn = tk.Menubutton(
            search_row, text=f"Sort: {self.sort_labels[self.sort_var.get()]}",
            font=self.font_normal, bg=COLORS["button_bg"], fg=COLORS["text"],
            activebackground=COLORS["accent"], activeforeground="white",
            relief="flat", borderwidth=0, padx=10, pady=4, indicatoron=False
        )
        sort_menu = tk.Menu(self.sort_btn, tearoff=0, bg=COLORS["bg_light"], fg=COLORS["text"],
                             activebackground=COLORS["accent"], activeforeground="white",
                             selectcolor="white", font=self.font_normal, borderwidth=0)
        for key, label in self.sort_labels.items():
            sort_menu.add_radiobutton(label=label, variable=self.sort_var, value=key,
                                       command=self._on_sort_change)
        self.sort_btn["menu"] = sort_menu
        self.sort_btn.pack(side="left", padx=(8, 0))

        self.file_tree = ttk.Treeview(
            right, columns=("name", "added", "size", "type"), show="headings", selectmode="extended"
        )
        self.file_tree.heading("name", text="Name", anchor="w")
        self.file_tree.heading("added", text="Date Added", anchor="w")
        self.file_tree.heading("size", text="Size", anchor="e")
        self.file_tree.heading("type", text="Type", anchor="e")
        self.file_tree.column("name", anchor="w", width=280, stretch=True)
        self.file_tree.column("added", anchor="w", width=140, stretch=False)
        self.file_tree.column("size", anchor="e", width=90, stretch=False)
        self.file_tree.column("type", anchor="e", width=70, stretch=False)
        self.file_tree.pack(fill="both", expand=True, padx=10)
        self.file_tree.bind("<Double-Button-1>", self.open_file)
        self.file_tree.bind("<Button-3>", self._show_file_context_menu)
        self.file_tree.bind("<ButtonPress-1>", self._file_press)
        self.file_tree.bind("<B1-Motion>", self._file_motion)
        self.file_tree.bind("<ButtonRelease-1>", self._file_release)
        self.file_tree.bind("<Motion>", self._on_file_hover_motion)
        self.file_tree.bind("<Leave>", self._on_file_hover_leave)

        self.file_tree.drop_target_register(DND_FILES)
        self.file_tree.dnd_bind("<<Drop>>", self._on_files_dropped)

        self.file_tree.drag_source_register(1, DND_FILES)
        self.file_tree.dnd_bind("<<DragInitCmd>>", self._on_drag_init)

        self.file_hint = tk.Label(right, text="", font=self.font_normal, bg=COLORS["bg"],
                                   fg=COLORS["text_muted"])
        self.file_hint.pack(padx=10, pady=(4, 0), anchor="w")

        btn_row_r = ttk.Frame(right)
        btn_row_r.pack(fill="x", padx=10, pady=8)
        ttk.Button(btn_row_r, text="+ File", command=self.add_file).pack(side="left", padx=2)
        ttk.Button(btn_row_r, text="Rename", command=self.rename_file).pack(side="left", padx=2)
        ttk.Button(btn_row_r, text="Delete", command=self.delete_file).pack(side="left", padx=2)
        ttk.Button(btn_row_r, text="Undo", command=self.undo_last).pack(side="left", padx=2)

    def _on_sort_change(self):
        self.sort_btn.config(text=f"Sort: {self.sort_labels[self.sort_var.get()]}")
        self.refresh_files()

    # ---------- Channels ----------

    def refresh_channels(self):
        self.channel_list.delete(0, "end")
        self._channel_names = list(self.meta.keys())
        for ch in self._channel_names:
            self.channel_list.insert("end", f"{ch} ({len(self.meta[ch])})")
        self.channel_hint.config(text="No channels yet — click + Channel." if not self._channel_names else "")

    def refresh_files(self):
        self.file_tree.delete(*self.file_tree.get_children())
        if self.current_channel:
            query = self.search_var.get().strip().lower()
            entries = self.meta[self.current_channel]
            rows = []
            for fname, entry in entries.items():
                info = storage.file_info(self.current_channel, fname, entry)
                if query and query not in info["display"].lower():
                    continue
                rows.append((fname, info))

            sort_mode = self.sort_var.get()
            if sort_mode == "alpha":
                rows.sort(key=lambda r: r[1]["display"].lower())
            elif sort_mode == "size":
                rows.sort(key=lambda r: r[1]["size"], reverse=True)
            else:
                rows.sort(key=lambda r: r[1]["added"], reverse=True)

            for fname, info in rows:
                self.file_tree.insert(
                    "", "end", iid=fname,
                    values=(info["display"], info["added"], info["size_text"], info["type"])
                )

            if not entries:
                self.file_hint.config(text="No files in this channel yet.")
            elif not rows:
                self.file_hint.config(text="No files match your search.")
            else:
                self.file_hint.config(text="")
        else:
            self.file_hint.config(text="Select a channel to see its files.")
        self.refresh_channel_bar()

    def on_select_channel(self, event):
        sel = self.channel_list.curselection()
        if sel:
            self.current_channel = self._channel_names[sel[0]]
            self.search_var.set("")
            self.refresh_files()

    def _on_channel_click(self, event):
        index = self.channel_list.nearest(event.y)
        if index < 0 or index >= self.channel_list.size():
            return
        bbox = self.channel_list.bbox(index)
        if not bbox or event.y > bbox[1] + bbox[3]:
            return
        if index in self.channel_list.curselection():
            self.channel_list.selection_clear(0, "end")
            self.current_channel = None
            self.search_var.set("")
            self.refresh_files()
            return "break"

    def _show_channel_context_menu(self, event):
        index = self.channel_list.nearest(event.y)
        if index < 0 or index >= len(self._channel_names):
            return
        bbox = self.channel_list.bbox(index)
        if not bbox or event.y > bbox[1] + bbox[3]:
            return
        self.channel_list.selection_clear(0, "end")
        self.channel_list.selection_set(index)
        self.current_channel = self._channel_names[index]
        self.search_var.set("")
        self.refresh_files()

        menu = tk.Menu(self, tearoff=0, bg=COLORS["bg_light"], fg=COLORS["text"],
                        activebackground=COLORS["accent"], activeforeground="white",
                        selectcolor="white", font=self.font_normal, borderwidth=0)
        menu.add_command(label="Export to Zip", command=self.export_channel)
        menu.add_separator()
        menu.add_command(label="Delete", command=self.delete_channel)
        menu.tk_popup(event.x_root, event.y_root)

    def add_channel(self):
        name = ask_string(self, "New Channel", "Channel name:", self.font_normal)
        if name and name not in self.meta:
            storage.create_channel(self.meta, name)
            self.refresh_channels()
            self._enforce_and_notify()

    def delete_channel(self):
        sel = self.channel_list.curselection()
        if not sel:
            return
        ch = self._channel_names[sel[0]]
        if ask_confirm(self, "Delete", f"Delete channel '{ch}' and all its files?", self.font_normal):
            storage.delete_channel(self.meta, ch)
            self.current_channel = None
            self.refresh_channels()
            self.refresh_files()
            self.refresh_overall_bar()
            self._enforce_and_notify()

    def export_channel(self):
        sel = self.channel_list.curselection()
        if not sel:
            show_info(self, "Info", "Select a channel first.", self.font_normal)
            return
        ch = self._channel_names[sel[0]]
        dest = filedialog.asksaveasfilename(
            defaultextension=".zip", initialfile=f"{ch}.zip",
            filetypes=[("Zip archive", "*.zip")]
        )
        if dest:
            if dest.lower().endswith(".zip"):
                dest = dest[:-4]
            storage.export_channel_zip(ch, dest)
            show_info(self, "Exported", f"Channel '{ch}' exported.", self.font_normal)

    # ---------- Files: add / duplicate check ----------

    def _add_files_to_channel(self, channel, paths):
        added = 0
        for path in paths:
            if not os.path.isfile(path):
                continue
            fname = os.path.basename(path)
            if storage.file_exists_in_channel(self.meta, channel, fname):
                proceed = ask_confirm(
                    self, "Duplicate file",
                    f"A file named '{fname}' already exists in '{channel}'. Add as a copy?",
                    self.font_normal, ok_label="Add Copy"
                )
                if not proceed:
                    continue
            storage.add_file(self.meta, channel, path)
            added += 1
        if added:
            self.refresh_channels()
            self.refresh_files()
            self.refresh_overall_bar()
            self._enforce_and_notify()

    def add_file(self):
        if not self.current_channel:
            show_info(self, "Info", "Select a channel first.", self.font_normal)
            return
        path = filedialog.askopenfilename()
        if path:
            self._add_files_to_channel(self.current_channel, [path])

    @staticmethod
    def _parse_dnd_paths(data):
        return [p.strip("{}") for p in re.findall(r"{[^}]*}|\S+", data)]

    def _on_files_dropped(self, event):
        if not self.current_channel:
            show_info(self, "Info", "Select a channel first, then drop files onto the list.", self.font_normal)
            return
        paths = self._parse_dnd_paths(event.data)
        self._add_files_to_channel(self.current_channel, paths)

    def _on_drag_init(self, event):
        """Fires when tkinterdnd2 detects a native OS drag starting on
        the file list. Hands it a copy-only file payload, and stands
        down our own in-app channel-drag tracking for this gesture so
        the two systems don't fight over the same mouse movement."""
        if not self.current_channel:
            return None
        sel = self.file_tree.selection()
        if not sel:
            return None

        if self._file_drag:
            if self._file_drag.get("highlight_idx") is not None:
                self.channel_list.itemconfig(self._file_drag["highlight_idx"], bg=COLORS["sidebar"])
            self._file_drag = None
        if self._drag_tooltip:
            self._drag_tooltip.destroy()
            self._drag_tooltip = None
        self.config(cursor="")

        paths = tuple(
            os.path.join(storage.channel_dir(self.current_channel), fname)
            for fname in sel
        )
        return ((COPY,), (DND_FILES,), paths)

    # ---------- Files: rename / delete / undo ----------

    def rename_file(self):
        sel = self.file_tree.selection()
        if not sel or not self.current_channel:
            return
        if len(sel) > 1:
            show_info(self, "Info", "Select exactly one file to rename.", self.font_normal)
            return
        fname = sel[0]
        display_old = self.meta[self.current_channel][fname]["display"]
        new_name = ask_string(self, "Rename", "New display name:", self.font_normal, initial=display_old)
        if new_name and new_name != display_old:
            storage.rename_file(self.meta, self.current_channel, fname, new_name)
            self._undo_stack.append({
                "type": "rename", "channel": self.current_channel,
                "fname": fname, "old": display_old, "new": new_name
            })
            self.refresh_files()

    def _handle_f2(self, event=None):
        if self.current_channel and len(self.file_tree.selection()) == 1:
            self.rename_file()

    def delete_file(self):
        sel = list(self.file_tree.selection())
        if not sel or not self.current_channel:
            return
        if len(sel) == 1:
            display = self.meta[self.current_channel][sel[0]]["display"]
            msg = f"Delete '{display}'?"
        else:
            msg = f"Delete {len(sel)} selected files?"
        if ask_confirm(self, "Delete", msg, self.font_normal):
            batch = [storage.soft_delete_file(self.meta, self.current_channel, fname) for fname in sel]
            self._undo_stack.append({"type": "delete", "batch": batch})
            self.refresh_channels()
            self.refresh_files()
            self.refresh_overall_bar()

    def undo_last(self):
        if not self._undo_stack:
            show_info(self, "Undo", "Nothing to undo.", self.font_normal)
            return
        action = self._undo_stack.pop()

        if action["type"] == "delete":
            for record in reversed(action["batch"]):
                storage.restore_file(self.meta, record)

        elif action["type"] == "rename":
            if action["channel"] in self.meta and action["fname"] in self.meta[action["channel"]]:
                storage.rename_file(self.meta, action["channel"], action["fname"], action["old"])

        elif action["type"] == "move":
            for mv in reversed(action["moves"]):
                if mv["dest_channel"] in self.meta and mv["dest_fname"] in self.meta[mv["dest_channel"]]:
                    storage.move_file(self.meta, mv["dest_channel"], mv["src_channel"], mv["dest_fname"])

        self.refresh_channels()
        self.refresh_files()
        self.refresh_overall_bar()

    def open_file(self, event):
        sel = self.file_tree.selection()
        if not sel or not self.current_channel:
            return
        fname = sel[0]
        path = os.path.join(storage.channel_dir(self.current_channel), fname)
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.call(["xdg-open", path])

    # ---------- Hover tooltip: real filename for renamed entries ----------

    def _on_file_hover_motion(self, event):
        row = self.file_tree.identify_row(event.y)
        if row != self._hover_row:
            self._hide_hover_tooltip()
            self._hover_row = row
            if row and self.current_channel:
                entry = self.meta[self.current_channel].get(row)
                if entry and entry.get("display") != row:
                    self._show_hover_tooltip(row, event.x_root, event.y_root)
        elif self._hover_tooltip:
            self._hover_tooltip.geometry(f"+{event.x_root + 12}+{event.y_root + 16}")

    def _on_file_hover_leave(self, event):
        self._hide_hover_tooltip()
        self._hover_row = None

    def _show_hover_tooltip(self, real_name, x_root, y_root):
        tip = tk.Toplevel(self)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        try:
            tip.attributes("-alpha", 0.85)
        except Exception:
            pass
        tk.Label(tip, text=real_name, bg=COLORS["bg_light"], fg=COLORS["text_muted"],
                 font=self.font_normal, padx=6, pady=3).pack()
        tip.geometry(f"+{x_root + 12}+{y_root + 16}")
        self._hover_tooltip = tip

    def _hide_hover_tooltip(self):
        if self._hover_tooltip:
            self._hover_tooltip.destroy()
            self._hover_tooltip = None

    # ---------- File selection / in-app drag-to-move ----------

    def _file_press(self, event):
        self._hide_hover_tooltip()
        row = self.file_tree.identify_row(event.y)
        self._file_drag = {"active": False, "start_x": event.x_root, "start_y": event.y_root,
                            "row": row, "pending_toggle": False, "highlight_idx": None}
        if not row:
            self.file_tree.selection_set(())
            return "break"

        current_sel = set(self.file_tree.selection())
        ctrl = bool(event.state & 0x0004)
        shift = bool(event.state & 0x0001)

        if ctrl:
            if row in current_sel:
                self.file_tree.selection_remove(row)
            else:
                self.file_tree.selection_add(row)
            return "break"

        if shift and current_sel:
            children = list(self.file_tree.get_children())
            anchor = self.file_tree.focus() or next(iter(current_sel))
            try:
                i1 = children.index(anchor)
                i2 = children.index(row)
            except ValueError:
                i1 = i2 = children.index(row)
            lo, hi = sorted((i1, i2))
            self.file_tree.selection_set(children[lo:hi + 1])
            return "break"

        if row in current_sel:
            self._file_drag["pending_toggle"] = True
            self.file_tree.focus(row)
            return "break"

        self.file_tree.selection_set(row)
        self.file_tree.focus(row)
        return "break"

    def _file_motion(self, event):
        drag = self._file_drag
        if not drag or not drag["row"]:
            return
        dx = abs(event.x_root - drag["start_x"])
        dy = abs(event.y_root - drag["start_y"])
        if not drag["active"] and (dx > 6 or dy > 6):
            drag["active"] = True
            self.config(cursor="hand2")
            sel = self.file_tree.selection()
            if len(sel) == 1:
                text = self.meta[self.current_channel][sel[0]]["display"]
            else:
                text = f"{len(sel)} files"
            self._start_drag_tooltip(text)

        if drag["active"]:
            if self._drag_tooltip:
                w = self._drag_tooltip.winfo_reqwidth()
                self._drag_tooltip.geometry(f"+{event.x_root - w // 2}+{event.y_root + 12}")

            widget = self.winfo_containing(event.x_root, event.y_root)
            idx = None
            if widget is self.channel_list:
                local_y = event.y_root - self.channel_list.winfo_rooty()
                candidate = self.channel_list.nearest(local_y)
                bbox = self.channel_list.bbox(candidate)
                if bbox and local_y <= bbox[1] + bbox[3]:
                    idx = candidate

            if idx != drag["highlight_idx"]:
                if drag["highlight_idx"] is not None:
                    self.channel_list.itemconfig(drag["highlight_idx"], bg=COLORS["sidebar"])
                if idx is not None:
                    self.channel_list.itemconfig(idx, bg=COLORS["accent_hover"])
                drag["highlight_idx"] = idx

    def _start_drag_tooltip(self, text):
        tip = tk.Toplevel(self)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tk.Label(tip, text=text, bg=COLORS["accent"], fg="white",
                 font=self.font_normal, padx=8, pady=4).pack()
        tip.update_idletasks()
        self._drag_tooltip = tip

    def _file_release(self, event):
        drag = self._file_drag
        self.config(cursor="")
        if self._drag_tooltip:
            self._drag_tooltip.destroy()
            self._drag_tooltip = None
        if not drag:
            return

        if drag["highlight_idx"] is not None:
            self.channel_list.itemconfig(drag["highlight_idx"], bg=COLORS["sidebar"])

        if drag["active"]:
            target_idx = drag["highlight_idx"]
            if target_idx is not None and self.current_channel:
                dest_channel = self._channel_names[target_idx]
                if dest_channel != self.current_channel:
                    moves = []
                    for fname in list(self.file_tree.selection()):
                        new_fname = storage.move_file(self.meta, self.current_channel, dest_channel, fname)
                        moves.append({
                            "src_channel": self.current_channel, "dest_channel": dest_channel,
                            "src_fname": fname, "dest_fname": new_fname
                        })
                    self._undo_stack.append({"type": "move", "moves": moves})
                    self.refresh_channels()
                    self.refresh_files()
                    self._enforce_and_notify()
            self._file_drag = None
            return

        if drag["pending_toggle"] and drag["row"]:
            sel = self.file_tree.selection()
            if list(sel) == [drag["row"]]:
                self.file_tree.selection_remove(drag["row"])
            else:
                self.file_tree.selection_set(drag["row"])
                self.file_tree.focus(drag["row"])

        self._file_drag = None

    def _show_file_context_menu(self, event):
        if not self.current_channel:
            return
        row = self.file_tree.identify_row(event.y)
        if not row:
            return
        if row not in self.file_tree.selection():
            self.file_tree.selection_set(row)
        self.file_tree.focus(row)

        menu = tk.Menu(self, tearoff=0, bg=COLORS["bg_light"], fg=COLORS["text"],
                        activebackground=COLORS["accent"], activeforeground="white",
                        selectcolor="white", font=self.font_normal, borderwidth=0)
        menu.add_command(label="Open", command=lambda: self.open_file(None))
        menu.add_command(label="Rename", command=self.rename_file)
        menu.add_separator()
        menu.add_command(label="Delete", command=self.delete_file)
        menu.tk_popup(event.x_root, event.y_root)

    # ---------- Storage bars & quota enforcement ----------

    def refresh_overall_bar(self):
        app_used, available = storage.app_used_and_available(self.meta)
        self.overall_bar.update_usage(
            app_used, available,
            storage.format_bytes(app_used), storage.format_bytes(available)
        )

    def refresh_channel_bar(self):
        quota = storage.channel_quota_bytes(self.meta)
        used = storage.channel_size_bytes(self.current_channel) if self.current_channel else 0
        self.channel_bar.update_usage(used, quota, storage.format_bytes(used), storage.format_bytes(quota))

    def _enforce_and_notify(self):
        trashed = storage.enforce_all_quotas(self.meta)
        if trashed:
            lines = [f"{ch}: " + ", ".join(names) for ch, names in trashed.items()]
            show_info(
                self, "Storage limit reached",
                "Some files were sent to the Recycle Bin to bring channels back under their fair-share quota:\n\n"
                + "\n".join(lines),
                self.font_normal
            )
            self.refresh_channels()
            self.refresh_files()
        self.refresh_overall_bar()
        self.refresh_channel_bar()

    def _on_close(self):
        storage.purge_session_trash()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()