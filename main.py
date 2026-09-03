from core import *
import customtkinter as ctk
from customtkinter import filedialog
import tkinter as tk
from tkinter import messagebox
from PIL import ImageTk, Image
from idlelib.tooltip import Hovertip
import webbrowser
from tkinterdnd2 import TkinterDnD, DND_FILES


def entry_undo(entry):
    """Perform undo action on the entry widget."""
    try:
        entry.event_generate("<<Undo>>")
    except tk.TclError:
        pass


def entry_redo(entry):
    """Perform redo action on the entry widget."""
    try:
        entry.event_generate("<<Redo>>")
    except tk.TclError:
        pass


def entry_cut(entry):
    """Perform cut action on the entry widget."""
    try:
        entry.event_generate("<<Cut>>")
    except tk.TclError:
        pass


def entry_copy(entry):
    """Perform copy action on the entry widget."""
    try:
        entry.event_generate("<<Copy>>")
    except tk.TclError:
        pass


def entry_paste(entry):
    """Perform paste action on the entry widget."""
    try:
        entry.event_generate("<<Paste>>")
    except tk.TclError:
        pass


def entry_delete_selection(entry):
    """Perform delete action on the entry selection."""
    try:
        entry.event_generate("<Delete>")
    except tk.TclError:
        pass


def entry_select_all(entry):
    """Select all text in the entry widget."""
    try:
        entry.select_range(0, "end")
        entry.icursor("end")
    except tk.TclError:
        pass
    return "break"


def setup_enhanced_entry(entry_widget):
    """Binds right-click context menu and keyboard shortcuts to standard entry widgets."""
    menu = tk.Menu(entry_widget, tearoff=0)

    menu.add_command(label="Undo\t\t", accelerator="Ctrl+Z", command=lambda: entry_undo(entry_widget))
    menu.add_command(label="Redo\t\t", accelerator="Ctrl+Y", command=lambda: entry_redo(entry_widget))
    menu.add_separator()
    menu.add_command(label="Cut\t\t", accelerator="Ctrl+X", command=lambda: entry_cut(entry_widget))
    menu.add_command(label="Copy\t\t", accelerator="Ctrl+C", command=lambda: entry_copy(entry_widget))
    menu.add_command(label="Paste\t\t", accelerator="Ctrl+V", command=lambda: entry_paste(entry_widget))
    menu.add_command(label="Delete\t\t", accelerator="Delete", command=lambda: entry_delete_selection(entry_widget))
    menu.add_separator()
    menu.add_command(label="Select All\t\t", accelerator="Ctrl+A", command=lambda: entry_select_all(entry_widget))

    def show_menu(event):
        menu.tk_popup(event.x_root, event.y_root)

    entry_widget.bind("<Button-3>", show_menu, add="+")

    def handle_ctrl_key(event):
        if event.state & 0x0004:
            code = event.keycode
            if code == 65:  # A
                entry_select_all(entry_widget)
                return "break"
            elif code == 90:  # Z
                entry_undo(entry_widget)
                return "break"
            elif code == 89:  # Y
                entry_redo(entry_widget)
                return "break"
            elif code == 67:  # C
                entry_copy(entry_widget)
                return "break"
            elif code == 88:  # X
                entry_cut(entry_widget)
                return "break"
            elif code == 86:  # V
                entry_paste(entry_widget)
                return "break"
        return None

    entry_widget.bind("<KeyPress>", handle_ctrl_key, add="+")


class ItemEditorModal(ctk.CTkToplevel):
    """Modal dialog for adding and editing listbox items with RTL support and shortcuts."""

    def __init__(self, parent, title_text, initial_text="", iconpath=None):
        super().__init__(parent)
        self.parent = parent
        self.result = None
        self.title(title_text)
        self.resizable(False, False)
        self.transient(parent)

        try:
            self.parent.attributes("-disabled", True)
        except Exception:
            pass

        if iconpath:
            self.after(250, lambda: self.iconphoto(False, iconpath))

        width = 460
        height = 145
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self.entry_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.entry_frame.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="nsew")
        self.entry_frame.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(
            self.entry_frame,
            height=36,
            font=("Segoe UI", 13),
            justify="right",
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.entry.insert(0, initial_text)
        setup_enhanced_entry(self.entry._entry)

        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="e")

        self.btn_cancel = ctk.CTkButton(
            self.button_frame,
            text="Cancel",
            width=75,
            height=30,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#A9A9A9",
            hover_color="#808080",
            text_color="#000000",
            command=self._on_cancel,
        )
        self.btn_cancel.grid(row=0, column=0, padx=(0, 10))

        self.btn_ok = ctk.CTkButton(
            self.button_frame,
            text="OK",
            width=75,
            height=30,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_ok,
        )
        self.btn_ok.grid(row=0, column=1)

        self.entry.bind("<Return>", lambda event: self._on_ok())
        self.entry.bind("<Escape>", lambda event: self._on_cancel())

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.grab_set()
        self.after(50, lambda: self.entry.focus_set())
        self.wait_window(self)

    def _on_ok(self):
        text = self.entry.get().strip()
        if not text:
            messagebox.showwarning("Invalid Input", "Input text cannot be empty or only spaces.", parent=self)
            self.entry.focus_set()
            return
        self.result = text
        self._close_modal()

    def _on_cancel(self):
        self.result = None
        self._close_modal()

    def _close_modal(self):
        try:
            self.parent.attributes("-disabled", False)
            self.parent.lift()
            self.parent.focus_force()
        except Exception:
            pass
        self.destroy()


class CTkListboxManager(ctk.CTkFrame):
    """Reusable Listbox container with Add, Edit, Remove, Clear All, Filter action buttons and alternating row colors."""

    def __init__(
        self,
        master,
        line_count=4,
        width=None,
        max_items=None,
        enable_scrollbar=True,
        enable_filter=False,
        get_icon_callback=None,
        on_change_callback=None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.max_items = max_items
        self.line_count = line_count
        self.custom_width = width
        self.enable_scrollbar = enable_scrollbar
        self.enable_filter = enable_filter
        self.get_icon_callback = get_icon_callback
        self.on_change_callback = on_change_callback
        self._is_enabled = True
        self._font_size = 12
        self._all_items = []
        self._is_filter_open = False
        self._filter_after_id = None
        self._is_updating_filter = False

        if self.custom_width:
            self.grid_columnconfigure(0, weight=0)
        else:
            self.grid_columnconfigure(0, weight=1)

        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)

        # Button toolbar at the top-left of the Listbox
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=(6, 4), sticky="w")

        app = self.winfo_toplevel()
        btn_font = app.btn_font_13 if hasattr(app, "btn_font_13") else ctk.CTkFont(size=13, weight="bold")

        self.btn_add = ctk.CTkButton(
            self.btn_frame, text="Add", width=60, height=26, font=btn_font, command=self.add_item
        )
        self.btn_add.grid(row=0, column=0, padx=(0, 4), pady=(0, 2))

        self.btn_edit = ctk.CTkButton(
            self.btn_frame, text="Edit", width=60, height=26, font=btn_font, command=self.edit_item
        )
        self.btn_edit.grid(row=0, column=1, padx=4, pady=(0, 2))

        self.btn_remove = ctk.CTkButton(
            self.btn_frame,
            text="Remove",
            width=74,
            height=26,
            font=btn_font,
            fg_color="#C0392B",
            hover_color="#962D22",
            command=self.remove_item,
        )
        self.btn_remove.grid(row=0, column=2, padx=4, pady=(0, 2))

        self.btn_clear = ctk.CTkButton(
            self.btn_frame,
            text="Clear All",
            width=82,
            height=26,
            font=btn_font,
            fg_color="#7F8C8D",
            hover_color="#626567",
            command=self.clear_all,
        )
        self.btn_clear.grid(row=0, column=3, padx=4, pady=(0, 2))

        if self.enable_filter:
            self.btn_filter = ctk.CTkButton(
                self.btn_frame,
                text="Filter",
                width=62,
                height=26,
                font=btn_font,
                anchor="center",
                fg_color="#0F6655",
                hover_color="#0B5042",
                command=self.toggle_filter_ui,
            )
            self.btn_filter.grid(row=0, column=4, padx=4, pady=(0, 2))

            # Filter Search Bar (hidden by default until user clicks Filter)
            self.filter_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.filter_frame.grid_columnconfigure(0, weight=1)
            self.filter_frame.grid_columnconfigure(1, weight=0)
            self.filter_frame.grid_columnconfigure(2, weight=0)

            self.filter_entry = ctk.CTkEntry(
                self.filter_frame,
                placeholder_text="Filter / Search items...",
                height=26,
                font=("Segoe UI", 12),
                justify="right",
            )
            self.filter_entry.grid(row=0, column=0, padx=(5, 4), pady=(0, 4), sticky="ew")
            setup_enhanced_entry(self.filter_entry._entry)

            # Bind only to the internal Tk entry to avoid recursive CustomTkinter callbacks.
            self.filter_entry._entry.bind("<KeyRelease>", self._on_filter_changed, add="+")
            self.filter_entry._entry.bind("<Escape>", lambda e: self.toggle_filter_ui(), add="+")

            self.lbl_filter_count = ctk.CTkLabel(
                self.filter_frame,
                text="",
                font=ctk.CTkFont(size=11),
                text_color="#888888",
            )
            self.lbl_filter_count.grid(row=0, column=1, padx=(0, 4), pady=(0, 4))

            self.btn_clear_filter = ctk.CTkButton(
                self.filter_frame,
                text="✕",
                width=24,
                height=24,
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="center",
                fg_color="#7F8C8D",
                hover_color="#626567",
                command=self.clear_filter,
            )
            self.btn_clear_filter.grid(row=0, column=2, padx=(0, 5), pady=(0, 4))

        # Direct Listbox mapping to prevent outer frame sizing issues
        listbox_kwargs = {
            "height": self.line_count,
            "font": ("Segoe UI", self._font_size),
            "justify": "right",
            "activestyle": "none",
            "highlightthickness": 1,
            "relief": "flat",
            "bd": 0,
        }
        if self.custom_width:
            listbox_kwargs["width"] = self.custom_width

        self.listbox = tk.Listbox(self, **listbox_kwargs)
        self.listbox.grid(row=2, column=0, padx=(5, 0), pady=0, sticky="nsew" if not self.custom_width else "w")

        if self.enable_scrollbar:
            self.scrollbar = ctk.CTkScrollbar(self, orientation="vertical", command=self.listbox.yview, width=12)
            self.scrollbar.grid(row=2, column=1, padx=(2, 5), pady=0, sticky="ns")
            self.listbox.configure(yscrollcommand=self.scrollbar.set)
        else:
            self.scrollbar = None

        self.listbox.bind("<Double-Button-1>", lambda event: self.edit_item())
        self.listbox.bind("<Delete>", lambda event: self.remove_item())

        self.apply_theme()
        ctk.AppearanceModeTracker.add(self.apply_theme)

    def toggle_filter_ui(self):
        if not self.enable_filter:
            return
        if self._is_filter_open:
            self._is_filter_open = False
            after_id = getattr(self, "_filter_after_id", None)
            if after_id is not None:
                try:
                    self.after_cancel(after_id)
                except tk.TclError:
                    pass
                self._filter_after_id = None
            try:
                self.filter_entry._entry.delete(0, "end")
            except tk.TclError:
                pass
            self._update_display_items()
            self.filter_frame.grid_forget()
            self.btn_filter.configure(fg_color="#0F6655", hover_color="#0B5042", text="Filter")
        else:
            self.filter_frame.grid(row=1, column=0, columnspan=2, padx=0, pady=(0, 4), sticky="ew")
            self._is_filter_open = True
            try:
                self.filter_entry._entry.delete(0, "end")
            except tk.TclError:
                pass
            self.btn_filter.configure(fg_color="#16A085", hover_color="#117A65", text="Filter ✓")
            try:
                self.filter_entry._entry.focus_set()
            except Exception:
                self.filter_entry.focus_set()
            self.after_idle(self._update_display_items)

    def clear_filter(self):
        if not self.enable_filter or not hasattr(self, "filter_entry"):
            return
        try:
            self.filter_entry._entry.delete(0, "end")
        except tk.TclError:
            return
        self._schedule_filter_update()

    def _on_filter_changed(self, event=None):
        if not self.enable_filter or not self._is_filter_open:
            return
        self._schedule_filter_update()

    def _schedule_filter_update(self):
        if not self.enable_filter or not self._is_filter_open:
            return

        after_id = getattr(self, "_filter_after_id", None)
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
            finally:
                self._filter_after_id = None

        self._filter_after_id = self.after_idle(self._update_display_items)

    def _get_filter_query(self):
        if not self.enable_filter or not self._is_filter_open or not hasattr(self, "filter_entry"):
            return ""
        try:
            query = self.filter_entry._entry.get()
        except tk.TclError:
            return ""
        if not query:
            return ""
        return query.strip().lower()

    def _update_display_items(self):
        self._filter_after_id = None

        if getattr(self, "_is_updating_filter", False):
            return
        if not hasattr(self, "listbox"):
            return

        self._is_updating_filter = True
        try:
            query = self._get_filter_query()

            current_sel = None
            try:
                selection = self.listbox.curselection()
                if selection:
                    current_sel = self.listbox.get(selection[0])
            except tk.TclError:
                return

            try:
                self.listbox.configure(state="normal")
                self.listbox.delete(0, "end")

                matched = 0
                restore_idx = None
                items = tuple(self._all_items)
                for item in items:
                    if not isinstance(item, str):
                        continue
                    if query and query not in item.lower():
                        continue
                    self.listbox.insert("end", item)
                    if current_sel == item and restore_idx is None:
                        restore_idx = matched
                    matched += 1

                if restore_idx is not None:
                    self.listbox.selection_set(restore_idx)

                self._refresh_colors()
                if not self._is_enabled:
                    self.listbox.configure(state="disabled")

                if hasattr(self, "lbl_filter_count") and self._is_filter_open:
                    total = len(items)
                    self.lbl_filter_count.configure(text=f"{matched}/{total}" if query else f"{total} items")
            except tk.TclError:
                return
        finally:
            self._is_updating_filter = False

    def apply_theme(self, new_mode=None):
        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            self.bg_even = "#242424"
            self.bg_odd = "#2D2D2D"
            self.fg = "#FFFFFF"
            self.sel_bg = "#1F6AA5"
            self.sel_fg = "#FFFFFF"
            self.disabled_bg = "#1A1A1A"
            self.disabled_fg = "#666666"
            self.highlight_color = "#3A3A3A"
        else:
            self.bg_even = "#FFFFFF"
            self.bg_odd = "#F2F2F2"
            self.fg = "#222222"
            self.sel_bg = "#1F6AA5"
            self.sel_fg = "#FFFFFF"
            self.disabled_bg = "#E6E6E6"
            self.disabled_fg = "#999999"
            self.highlight_color = "#C0C0C0"

        self.listbox.configure(
            bg=self.bg_even if self._is_enabled else self.disabled_bg,
            fg=self.fg if self._is_enabled else self.disabled_fg,
            highlightbackground=self.highlight_color,
            highlightcolor=self.sel_bg,
            selectbackground=self.sel_bg,
            selectforeground=self.sel_fg,
        )
        self._refresh_colors()

    def _refresh_colors(self):
        if not self._is_enabled:
            self.listbox.configure(bg=self.disabled_bg, fg=self.disabled_fg)
            return

        for i in range(self.listbox.size()):
            row_bg = self.bg_even if i % 2 == 0 else self.bg_odd
            self.listbox.itemconfigure(i, background=row_bg, foreground=self.fg)

    def set_font_size(self, size):
        if self.custom_width is not None:
            return
        self._font_size = size
        self.listbox.configure(font=("Segoe UI", self._font_size))

    def set_state(self, is_enabled):
        self._is_enabled = is_enabled
        btn_state = "normal" if is_enabled else "disabled"
        self.btn_add.configure(state=btn_state)
        self.btn_edit.configure(state=btn_state)
        self.btn_remove.configure(state=btn_state)
        self.btn_clear.configure(state=btn_state)
        if hasattr(self, "btn_filter"):
            self.btn_filter.configure(state=btn_state)
        if hasattr(self, "filter_entry"):
            self.filter_entry.configure(state=btn_state)
        if hasattr(self, "btn_clear_filter"):
            self.btn_clear_filter.configure(state=btn_state)
        self.listbox.configure(state="normal" if is_enabled else "disabled")
        self._refresh_colors()

    def get_items(self):
        return list(self._all_items)

    def get_items_text(self):
        return "\n".join(self.get_items())

    def set_items(self, items):
        self._all_items = []
        for item in items:
            if item.strip():
                if self.max_items and len(self._all_items) >= self.max_items:
                    break
                self._all_items.append(item.strip())
        self._update_display_items()

    def set_items_from_text(self, text):
        items = [line.strip() for line in text.split("\n") if line.strip()]
        self.set_items(items)

    def add_item(self):
        if not self._is_enabled:
            return
        if self.max_items and len(self._all_items) >= self.max_items:
            messagebox.showwarning("Limit Reached", f"Maximum {self.max_items} item(s) allowed.")
            return

        icon = self.get_icon_callback() if self.get_icon_callback else None
        dialog = ItemEditorModal(self.winfo_toplevel(), "Add Item", "", iconpath=icon)
        if dialog.result:
            self._all_items.append(dialog.result)
            self._update_display_items()
            if self.on_change_callback:
                self.on_change_callback()

    def edit_item(self):
        if not self._is_enabled:
            return
        selected_idx = self.listbox.curselection()
        if not selected_idx:
            messagebox.showinfo("Select Item", "Please select an item from the list to edit.")
            return

        idx = selected_idx[0]
        current_val = self.listbox.get(idx)
        icon = self.get_icon_callback() if self.get_icon_callback else None
        dialog = ItemEditorModal(self.winfo_toplevel(), "Edit Item", current_val, iconpath=icon)
        if dialog.result:
            if current_val in self._all_items:
                all_idx = self._all_items.index(current_val)
                self._all_items[all_idx] = dialog.result
            self._update_display_items()
            if self.on_change_callback:
                self.on_change_callback()

    def remove_item(self):
        if not self._is_enabled:
            return
        selected_idx = self.listbox.curselection()
        if not selected_idx:
            messagebox.showinfo("Select Item", "Please select an item from the list to remove.")
            return

        idx = selected_idx[0]
        val = self.listbox.get(idx)
        confirm = messagebox.askyesno("Confirm Removal", f'Are you sure you want to remove:\n\n"{val}"?')
        if confirm:
            if val in self._all_items:
                self._all_items.remove(val)
            self._update_display_items()
            if self.on_change_callback:
                self.on_change_callback()

    def clear_all(self):
        if not self._is_enabled:
            return
        if len(self._all_items) == 0:
            return

        confirm = messagebox.askyesno("Confirm Clear All", "Are you sure you want to remove all items from this list?")
        if confirm:
            self._all_items.clear()
            self._update_display_items()
            if self.on_change_callback:
                self.on_change_callback()


class CTkDualScrollableFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("corner_radius", 0)
        super().__init__(master, **kwargs)

        self._theme_bg = self._get_theme_bg()
        self.configure(fg_color=self._theme_bg, bg_color=self._theme_bg, corner_radius=0)

        self.canvas = tk.Canvas(self, bg=self._theme_bg, highlightthickness=0, bd=0, relief="flat", insertwidth=0)
        self.vsb = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview)
        self.hsb = ctk.CTkScrollbar(self, orientation="horizontal", command=self.canvas.xview)

        self.canvas.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)

        self.inner_frame = ctk.CTkFrame(self.canvas, fg_color=self._theme_bg, bg_color=self._theme_bg, corner_radius=0)
        self.inner_window = self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")

        self.corner_fill = tk.Frame(self, bg=self._theme_bg, bd=0, highlightthickness=0)

        self.canvas.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.inner_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", self._bind_mouse_scroll)
        self.canvas.bind("<Leave>", self._unbind_mouse_scroll)
        self.inner_frame.bind("<Enter>", self._bind_mouse_scroll)
        self.inner_frame.bind("<Leave>", self._unbind_mouse_scroll)

        ctk.AppearanceModeTracker.add(self._update_canvas_bg)
        self.after_idle(self._update_canvas_bg)

    def _get_theme_bg(self):
        color = ctk.ThemeManager.theme["CTkFrame"]["fg_color"]
        if isinstance(color, (list, tuple)):
            color = color[1 if ctk.get_appearance_mode() == "Dark" else 0]
        return color

    def _update_canvas_bg(self, new_appearance_mode=None):
        self._theme_bg = self._get_theme_bg()
        self.configure(fg_color=self._theme_bg, bg_color=self._theme_bg)
        self.canvas.configure(bg=self._theme_bg)
        self.corner_fill.configure(bg=self._theme_bg)

        if self.inner_frame.winfo_exists():
            try:
                self.inner_frame.configure(fg_color=self._theme_bg, bg_color=self._theme_bg)
            except Exception:
                pass
            self._propagate_appearance(self.inner_frame, ctk.get_appearance_mode())

        self.after_idle(self._check_scrollbars)

    def _propagate_appearance(self, widget, mode):
        try:
            if hasattr(widget, "_set_appearance_mode"):
                widget._set_appearance_mode(mode)
        except Exception:
            pass

        for child in widget.winfo_children():
            if isinstance(child, (ctk.CTkTextbox, tk.Listbox)):
                continue
            self._propagate_appearance(child, mode)

    def _update_inner_width(self, canvas_width):
        if getattr(self, "_is_updating_width", False):
            return
        self._is_updating_width = True
        try:
            content_width = self.inner_frame.winfo_reqwidth()
            target_width = canvas_width if content_width <= canvas_width else content_width
            current_width = self.canvas.itemcget(self.inner_window, "width")
            try:
                current_width = int(float(current_width))
            except (ValueError, TypeError):
                current_width = -1
            if current_width != int(target_width):
                self.canvas.itemconfigure(self.inner_window, width=target_width)
        finally:
            self._is_updating_width = False

    def _on_frame_configure(self, event=None):
        self._update_inner_width(self.canvas.winfo_width())
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._check_scrollbars()

    def _on_canvas_configure(self, event):
        self._update_inner_width(event.width)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._check_scrollbars()

    def _check_scrollbars(self):
        if getattr(self, "_is_checking_scrollbars", False):
            return
        self._is_checking_scrollbars = True
        try:
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()

            if canvas_w <= 1 or canvas_h <= 1:
                return

            content_w = self.inner_frame.winfo_reqwidth()
            content_h = self.inner_frame.winfo_reqheight()

            show_v = content_h > canvas_h
            show_h = content_w > canvas_w

            is_v_shown = bool(self.vsb.winfo_ismapped())
            is_h_shown = bool(self.hsb.winfo_ismapped())

            if show_v and not is_v_shown:
                self.vsb.grid(row=0, column=1, sticky="ns", padx=0, pady=0)
            elif not show_v and is_v_shown:
                self.vsb.grid_forget()

            if show_h and not is_h_shown:
                self.hsb.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
            elif not show_h and is_h_shown:
                self.hsb.grid_forget()

            is_corner_shown = bool(self.corner_fill.winfo_ismapped())
            if show_v and show_h:
                if not is_corner_shown:
                    self.corner_fill.grid(row=1, column=1, sticky="nsew")
            else:
                if is_corner_shown:
                    self.corner_fill.grid_forget()

            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        finally:
            self._is_checking_scrollbars = False

    def _bind_mouse_scroll(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mouse_scroll(self, event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        if not self.vsb.winfo_ismapped():
            return

        if getattr(event, "num", None) == 4:
            self.canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            self.canvas.yview_scroll(1, "units")
        elif event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.delta < 0:
            self.canvas.yview_scroll(1, "units")


class CustomTkinterDnD(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)


class PersianSubtitleToolkit(CustomTkinterDnD):
    def __init__(self):
        super().__init__()

        self._last_width = 0
        self._last_height = 0

        self.attributes("-alpha", 0.0)

        self.lock = AppLock(APP_NAME)
        if not self.lock.acquire():
            temp_root = tk.Tk()
            temp_root.withdraw()
            messagebox.showwarning(
                f"{APP_NAME} v{APP_VERSION}",
                f"{APP_NAME} is already running.\nOnly one instance is allowed.",
            )
            temp_root.destroy()
            sys.exit(0)

        self.lock.start_updater()

        self.title(f"{APP_NAME} v{APP_VERSION}")

        temp_dir = os.path.dirname(__file__)
        try:
            self.iconpath = ImageTk.PhotoImage(file=self.resource_path(os.path.join(temp_dir, "assets", "icon.png")))
            heart_path = self.resource_path(os.path.join(temp_dir, "assets", "heart.png"))
            img = Image.open(heart_path)
            width_img, height_img = img.size
            self.heart_image = ctk.CTkImage(
                light_image=Image.open(heart_path), dark_image=Image.open(heart_path), size=(width_img, height_img)
            )

            self.heart_icon = ImageTk.PhotoImage(file=heart_path)
            self.wm_iconbitmap()
            self.iconphoto(False, self.iconpath)
        except Exception:
            self.iconpath = None
            self.heart_image = None
            print("Warning: Could not load application icons.")

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_idletasks()

        self.resizable(True, True)
        self.minsize(800, 600)

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)

        self.grid_columnconfigure(0, weight=1)
        self.create_widget()

        self.config_manager = ConfigManager(CONFIG_FILE, DEFAULT_CONFIG)
        self.load_config()

        self.after(100, lambda: self.start_btn.focus_set())
        self.after(200, lambda: self.attributes("-alpha", 1.0))

        self.bind("<Configure>", self.adjust_button_fonts, add="+")

    def adjust_button_fonts(self, event):
        """Dynamically scale button and listbox fonts only when width actually changes (prevents flicker)."""
        if event.widget == self:
            if event.width == self._last_width and event.height == self._last_height:
                return

            self._last_width = event.width
            self._last_height = event.height

            base_width = 800
            current_width = event.width
            scale = max(1.0, min(1.3, current_width / base_width))

            self.btn_font_13.configure(size=int(13 * scale))
            self.btn_font_14.configure(size=int(14 * scale))
            self.btn_font_15.configure(size=int(15 * scale))
            self.btn_font_16.configure(size=int(16 * scale))
            self.btn_font_18.configure(size=int(18 * scale))

            listbox_font_size = int(12 * scale)
            self.lst_bypass.set_font_size(listbox_font_size)
            self.lst_remove.set_font_size(listbox_font_size)
            self.lst_replace.set_font_size(listbox_font_size)
            self.lst_intro_credit.set_font_size(12)

    def on_tab_changed(self):
        if self.tabview.get() == "Process":
            self.after(10, lambda: self.start_btn.focus_set())

    def create_widget(self):
        font_bold = ctk.CTkFont(size=14, weight="bold")

        self.btn_font_13 = ctk.CTkFont(size=13, weight="bold")
        self.btn_font_14 = ctk.CTkFont(size=14, weight="bold")
        self.btn_font_15 = ctk.CTkFont(size=15, weight="bold")
        self.btn_font_16 = ctk.CTkFont(size=16, weight="bold")
        self.btn_font_18 = ctk.CTkFont(size=18, weight="bold")

        # --- Top Container (Row 0) ---
        self.top_container = ctk.CTkFrame(self, fg_color="transparent")
        self.top_container.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="nsew")

        self.top_container.grid_columnconfigure(0, weight=60)
        self.top_container.grid_columnconfigure(1, weight=1)
        self.top_container.grid_columnconfigure(2, weight=1)

        self.path_entry = ctk.CTkEntry(
            self.top_container,
            height=35,
            placeholder_text="Select Source Folder Which Contains Subtitles",
            font=font_bold,
        )
        self.path_entry.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")
        self.path_entry.configure(state="readonly")

        self.browse_btn = ctk.CTkButton(self.top_container, text="Browse", height=35, font=self.btn_font_14)
        self.browse_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.browse_btn.configure(command=self.browse_folder)

        self.theme_frame = ctk.CTkFrame(self.top_container, fg_color="transparent")
        self.theme_frame.grid(row=0, column=2, padx=(5, 0), pady=0, sticky="nsew")
        self.theme_frame.grid_columnconfigure(0, weight=1)
        self.theme_frame.grid_columnconfigure(1, weight=1)
        self.theme_frame.grid_rowconfigure(0, weight=1)
        self.theme_frame.grid_rowconfigure(1, weight=1)

        self.theme_label = ctk.CTkLabel(self.theme_frame, text="Dark Mode", font=ctk.CTkFont(size=12, weight="bold"))
        self.theme_label.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self.theme_switch = ctk.CTkSwitch(self.theme_frame, text="", command=self.change_theme, width=45)
        self.theme_switch.grid(row=0, column=1, sticky="ew")
        self.theme_switch.select()

        self.log_label = ctk.CTkLabel(self.theme_frame, text="Save Logs", font=ctk.CTkFont(size=12, weight="bold"))
        self.log_label.grid(row=1, column=0, padx=(0, 5), sticky="ew")
        self.log_switch = ctk.CTkSwitch(self.theme_frame, text="", command=self.toggle_logs, width=45)
        self.log_switch.grid(row=1, column=1, sticky="ew")
        self.log_switch.configure(state="disabled")

        # --- Middle Container (Row 1) with CTkTabview ---
        self.middle_container = ctk.CTkFrame(self)
        self.middle_container.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        self.middle_container.grid_rowconfigure(0, weight=1)
        self.middle_container.grid_columnconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self.middle_container)
        self.tabview.grid(row=0, column=0, padx=5, pady=(0, 10), sticky="nsew")
        self.tabview.configure(command=self.on_tab_changed)

        self.tab_preprocess = self.tabview.add("Pre-Process")
        self.tab_process = self.tabview.add("Process")
        self.tab_postprocess = self.tabview.add("Post-Process")
        self.tab_extra = self.tabview.add("Extra Options")

        self.tabview._segmented_button.configure(font=ctk.CTkFont(size=15, weight="bold"))
        self.tabview._segmented_button.grid(
            padx=0,
            pady=0,
            ipadx=5,
            ipady=5,
            sticky="nsew",
        )

        for tab in [self.tab_preprocess, self.tab_process, self.tab_postprocess, self.tab_extra]:
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        # --- Pre-Process Tab ---
        self.preprocess_inner_frame = CTkDualScrollableFrame(self.tab_preprocess)
        self.preprocess_inner_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.preprocess_inner_frame.grid_columnconfigure(0, weight=1)

        preprocess_parent = self.preprocess_inner_frame.inner_frame

        self.chk_remove_alignment_tags = ctk.CTkCheckBox(
            preprocess_parent,
            text="Remove Alignment Tags (e.g., {\\an8}, {\\an9})",
            font=font_bold,
        )
        self.chk_remove_alignment_tags.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.chk_trim_spaces = ctk.CTkCheckBox(
            preprocess_parent,
            text="Trim spaces from beginning and end of lines (Pre-Process)",
            font=font_bold,
        )
        self.chk_trim_spaces.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        self.chk_fix_misplaced_chars = ctk.CTkCheckBox(
            preprocess_parent,
            text="Fix Misplaced Chars (e.g., ؟سلام ➔ سلام؟) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_fix_misplaced_chars.grid(row=2, column=0, padx=5, pady=5, sticky="w")

        self.chk_fix_abbreviations = ctk.CTkCheckBox(
            preprocess_parent,
            text="Fix Abbreviations (e.g., F. B. I. ➔ F.B.I.)  - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_fix_abbreviations.grid(row=3, column=0, padx=5, pady=5, sticky="w")

        self.chk_comma_fixes = ctk.CTkCheckBox(
            preprocess_parent,
            text="Comma Fixes (e.g., سلام , دنیا ➔ سلام، دنیا) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_comma_fixes.grid(row=4, column=0, padx=5, pady=5, sticky="w")

        self.chk_exclamation_fixes = ctk.CTkCheckBox(
            preprocess_parent,
            text="Exclamation Mark Fixes (e.g., سلام ! ➔ سلام!) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_exclamation_fixes.grid(row=5, column=0, padx=5, pady=5, sticky="w")

        self.chk_parentheses_fixes = ctk.CTkCheckBox(
            preprocess_parent,
            text="Parentheses Fixes (e.g., ( متن ) ➔ (متن)) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_parentheses_fixes.grid(row=6, column=0, padx=5, pady=5, sticky="w")

        self.chk_question_mark_fixes = ctk.CTkCheckBox(
            preprocess_parent,
            text="Question Mark Fixes (e.g., چرا ؟؟ ➔ چرا؟) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_question_mark_fixes.grid(row=7, column=0, padx=5, pady=5, sticky="w")

        self.chk_double_quotes_fixes = ctk.CTkCheckBox(
            preprocess_parent,
            text='Double-Quotes Fixes (e.g., "سلام" ➔ «سلام») - (Triggers Post-Process UTF-8)',
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_double_quotes_fixes.grid(row=8, column=0, padx=5, pady=5, sticky="w")

        self.chk_dash_fixes = ctk.CTkCheckBox(
            preprocess_parent,
            text="Dash Fixes (e.g., -- ➔ —) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_dash_fixes.grid(row=9, column=0, padx=5, pady=5, sticky="w")

        self.chk_comments_fixes = ctk.CTkCheckBox(
            preprocess_parent,
            text="Comments Fixes (e.g., [موسیقی] ➔ حذف) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_comments_fixes.grid(row=10, column=0, padx=5, pady=5, sticky="w")

        self.chk_dialog_hyphen_fix = ctk.CTkCheckBox(
            preprocess_parent,
            text="Dialog Hyphen Fix (e.g., -سلام ➔ - سلام) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_dialog_hyphen_fix.grid(row=11, column=0, padx=5, pady=5, sticky="w")

        self.chk_remove_standalone_dots = ctk.CTkCheckBox(
            preprocess_parent,
            text="Remove Standalone Dots at the beginning and end of lines (e.g., .سلام. ➔ سلام)",
            font=font_bold,
        )
        self.chk_remove_standalone_dots.grid(row=12, column=0, padx=5, pady=5, sticky="w")

        self.chk_remove_unneeded_spaces = ctk.CTkCheckBox(
            preprocess_parent,
            text="Remove Unneeded Spaces (Converts multiple spaces into one)",
            font=font_bold,
        )
        self.chk_remove_unneeded_spaces.grid(row=13, column=0, padx=5, pady=5, sticky="w")

        self.chk_persian_question_mark_and_comma = ctk.CTkCheckBox(
            preprocess_parent,
            text="Convert English Question Marks and Commas to Persian (e.g., ?, ➔ ؟،) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_persian_question_mark_and_comma.grid(row=14, column=0, padx=5, pady=5, sticky="w")

        self.chk_arabic_char = ctk.CTkCheckBox(
            preprocess_parent,
            text="Convert Arabic Characters to Persian (e.g., ي، ك ➔ ی، ک) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_arabic_char.grid(row=15, column=0, padx=5, pady=5, sticky="w")

        self.chk_arabic_num = ctk.CTkCheckBox(
            preprocess_parent,
            text="Convert Arabic Numerals to Persian Numerals (e.g., ٤ ➔ ۴) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_arabic_num.grid(row=16, column=0, padx=5, pady=5, sticky="w")

        self.chk_english_num = ctk.CTkCheckBox(
            preprocess_parent,
            text="Convert English Numerals to Persian (e.g., 4 ➔ ۴) (Excludes Tags/Timecodes/Letter-attached numbers) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_english_num.grid(row=17, column=0, padx=5, pady=5, sticky="w")

        self.chk_space_to_invisible_space = ctk.CTkCheckBox(
            preprocess_parent,
            text="Space to Invisible Space (e.g., شود می ➔ می‌شود) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_space_to_invisible_space.grid(row=18, column=0, padx=5, pady=5, sticky="w")

        self.chk_hexre_fixes = ctk.CTkCheckBox(
            preprocess_parent,
            text="Fix Common Hexre Typo Errors (e.g., برایه ➔ برایِ) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_hexre_fixes.grid(row=19, column=0, padx=5, pady=5, sticky="w")

        self.chk_add_missing_spaces = ctk.CTkCheckBox(
            preprocess_parent,
            text="Add Missing Spaces (e.g., word.word ➔ word. word)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_add_missing_spaces.grid(row=20, column=0, padx=5, pady=5, sticky="w")

        # --- Process Tab ---
        self.process_inner_frame = CTkDualScrollableFrame(self.tab_process)
        self.process_inner_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.process_inner_frame.grid_columnconfigure(0, weight=1)

        process_parent = self.process_inner_frame.inner_frame
        process_parent.grid_columnconfigure(0, weight=1)

        # Bypass List
        self.chk_bypass = ctk.CTkCheckBox(
            process_parent,
            text="Bypass List (Skip lines matching these words)",
            font=font_bold,
            command=self.toggle_bypass,
        )
        self.chk_bypass.grid(row=0, column=0, padx=5, pady=(5, 3), sticky="w")

        self.lst_bypass = CTkListboxManager(
            process_parent,
            line_count=4,
            enable_scrollbar=True,
            enable_filter=True,
            get_icon_callback=lambda: self.iconpath,
            on_change_callback=self.save_config,
        )
        self.lst_bypass.grid(row=1, column=0, padx=5, pady=(0, 10), sticky="ew")

        # Remove List
        self.chk_remove = ctk.CTkCheckBox(
            process_parent,
            text="Remove List (Delete entire line if matching these words)",
            font=font_bold,
            command=self.toggle_remove,
        )
        self.chk_remove.grid(row=2, column=0, padx=5, pady=(5, 3), sticky="w")

        self.lst_remove = CTkListboxManager(
            process_parent,
            line_count=4,
            enable_scrollbar=True,
            enable_filter=True,
            get_icon_callback=lambda: self.iconpath,
            on_change_callback=self.save_config,
        )
        self.lst_remove.grid(row=3, column=0, padx=5, pady=(0, 10), sticky="ew")

        # Replace List
        self.chk_replace = ctk.CTkCheckBox(
            process_parent,
            text="Replace List (Remove these specific words from matching lines)",
            font=font_bold,
            command=self.toggle_replace,
        )
        self.chk_replace.grid(row=4, column=0, padx=5, pady=(5, 3), sticky="w")

        self.lst_replace = CTkListboxManager(
            process_parent,
            line_count=4,
            enable_scrollbar=True,
            enable_filter=True,
            get_icon_callback=lambda: self.iconpath,
            on_change_callback=self.save_config,
        )
        self.lst_replace.grid(row=5, column=0, padx=5, pady=(0, 10), sticky="ew")

        # --- Post-Process Tab ---
        self.postprocess_inner_frame = CTkDualScrollableFrame(self.tab_postprocess)
        self.postprocess_inner_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.postprocess_inner_frame.grid_columnconfigure(0, weight=1)

        post_parent = self.postprocess_inner_frame.inner_frame
        post_parent.grid_columnconfigure(0, weight=1)

        self.chk_post_trim_spaces = ctk.CTkCheckBox(
            post_parent,
            text="Trim spaces from beginning and end of lines (Post-Process)",
            font=font_bold,
        )
        self.chk_post_trim_spaces.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.chk_remove_empty_tags = ctk.CTkCheckBox(
            post_parent,
            text="Remove Empty HTML Tags (e.g., <font></font>, <b></b>)",
            font=font_bold,
        )
        self.chk_remove_empty_tags.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        self.chk_remove_negative_timecodes = ctk.CTkCheckBox(
            post_parent,
            text="Remove Negative Timecodes - (Triggers Reformat & Renumber)",
            font=font_bold,
            command=self.on_reformat_dependency_toggle,
        )
        self.chk_remove_negative_timecodes.grid(row=2, column=0, padx=5, pady=5, sticky="w")

        self.chk_fix_misplaced_timecodes = ctk.CTkCheckBox(
            post_parent,
            text="Fix Misplaced Timecodes (Reorder blocks & remove empty ones) - (Triggers Reformat & Renumber)",
            font=font_bold,
            command=self.on_reformat_dependency_toggle,
        )
        self.chk_fix_misplaced_timecodes.grid(row=3, column=0, padx=5, pady=5, sticky="w")

        self.chk_remove_duplicate_subtitles = ctk.CTkCheckBox(
            post_parent,
            text="Remove Duplicate Subtitles (Removes exact matches of timecode and text) - (Triggers Reformat & Renumber)",
            font=font_bold,
            command=self.on_reformat_dependency_toggle,
        )
        self.chk_remove_duplicate_subtitles.grid(row=4, column=0, padx=5, pady=5, sticky="w")

        self.chk_fix_overlapping_timecodes = ctk.CTkCheckBox(
            post_parent,
            text="Fix Overlapping Timecodes (Adjusts end timecode to prevent simultaneous display) - (Triggers Reformat & Renumber)",
            font=font_bold,
            command=self.on_reformat_dependency_toggle,
        )
        self.chk_fix_overlapping_timecodes.grid(row=5, column=0, padx=5, pady=5, sticky="w")

        self.chk_remove_empty_subtitles = ctk.CTkCheckBox(
            post_parent,
            text="Remove Empty Subtitles - (Triggers Reformat & Renumber)",
            font=font_bold,
            command=self.on_reformat_dependency_toggle,
        )
        self.chk_remove_empty_subtitles.grid(row=6, column=0, padx=5, pady=5, sticky="w")

        self.intro_credit_frame = ctk.CTkFrame(post_parent, fg_color="transparent")
        self.intro_credit_frame.grid(row=7, column=0, padx=5, pady=(0, 3), sticky="w")

        self.chk_add_intro_credit = ctk.CTkCheckBox(
            self.intro_credit_frame,
            text="Add Intro Credit Subtitle (Max 2 Lines) - (Triggers Reformat & Renumber)",
            font=font_bold,
            command=self.on_reformat_dependency_toggle,
        )
        self.chk_add_intro_credit.grid(row=0, column=0, padx=(0, 10), pady=2, sticky="w")

        self.lbl_intro_credit_duration = ctk.CTkLabel(
            self.intro_credit_frame,
            text="Duration (sec):",
            font=font_bold,
        )
        self.lbl_intro_credit_duration.grid(row=0, column=1, padx=(60, 5), pady=2, sticky="w")

        self.opt_intro_credit_duration = ctk.CTkOptionMenu(
            self.intro_credit_frame,
            values=["2", "3", "4", "5", "6", "7", "8", "9", "10"],
            width=65,
            command=lambda _: self.save_config(),
        )
        self.opt_intro_credit_duration.grid(row=0, column=2, padx=0, pady=2, sticky="w")
        self.opt_intro_credit_duration.set("8")

        self.lst_intro_credit = CTkListboxManager(
            post_parent,
            line_count=2,
            width=80,
            max_items=2,
            enable_scrollbar=False,
            get_icon_callback=lambda: self.iconpath,
            on_change_callback=self.save_config,
        )
        self.lst_intro_credit.grid(row=8, column=0, padx=5, pady=(0, 10), sticky="w")

        self.chk_reformat_renumber = ctk.CTkCheckBox(
            post_parent,
            text="Reformat and Renumber Subtitles (Fixes numbering order and cleans block spacing)",
            font=font_bold,
            command=self.on_reformat_renumber_toggle,
        )
        self.chk_reformat_renumber.grid(row=9, column=0, padx=5, pady=5, sticky="w")

        self.chk_force_rtl = ctk.CTkCheckBox(
            post_parent,
            text="Force RTL (Remove control characters and apply RTL mark) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_force_rtl.grid(row=10, column=0, padx=5, pady=5, sticky="w")

        self.chk_encode_utf8 = ctk.CTkCheckBox(
            post_parent,
            text="Save Final File with UTF-8 Encoding (Required for seamless Persian characters rendering)",
            font=font_bold,
            command=self.on_utf8_toggle,
        )
        self.chk_encode_utf8.grid(row=11, column=0, padx=5, pady=5, sticky="w")

        # --- Extra Options Tab ---
        self.extra_inner_frame = CTkDualScrollableFrame(self.tab_extra)
        self.extra_inner_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.extra_inner_frame.grid_columnconfigure(0, weight=1)

        extra_parent = self.extra_inner_frame.inner_frame
        extra_parent.grid_columnconfigure(0, weight=1)

        self.chk_delete_original = ctk.CTkCheckBox(
            extra_parent, text="Delete original subtitle file after successful process", font=font_bold
        )
        self.chk_delete_original.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.chk_detailed_logs = ctk.CTkCheckBox(
            extra_parent,
            text='Create individual changelog file for each subtitle (Saved in "/Logs/Subtitle-Logs/" folder)',
            font=font_bold,
        )
        self.chk_detailed_logs.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        self.chk_enable_dnd = ctk.CTkCheckBox(
            extra_parent,
            text="Enable Drag and Drop for Files and Folders on Process buttons",
            font=font_bold,
        )
        self.chk_enable_dnd.grid(row=2, column=0, padx=5, pady=5, sticky="w")

        self.chk_convert_ass_comments = ctk.CTkCheckBox(
            extra_parent,
            text="Convert Comment lines in ASS subtitles (Disabled: only Dialogue lines are converted)",
            font=font_bold,
        )
        self.chk_convert_ass_comments.grid(row=3, column=0, padx=5, pady=5, sticky="w")

        self.chk_delete_converted_temp_files = ctk.CTkCheckBox(
            extra_parent,
            text="Delete temporary SRT files created from non-SRT subtitles after processing",
            font=font_bold,
        )
        self.chk_delete_converted_temp_files.grid(row=4, column=0, padx=5, pady=5, sticky="w")

        # --- Progress Container (Row 2) ---
        self.progress_container = ctk.CTkFrame(self, fg_color="transparent")
        self.progress_container.grid(row=2, column=0, padx=10, pady=0, sticky="nsew")

        self.progress_container.grid_columnconfigure(0, weight=9)
        self.progress_container.grid_columnconfigure(1, weight=1)
        self.progress_container.grid_rowconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(self.progress_container, height=12)
        self.progress_bar.grid(row=0, column=0, padx=(5, 10), pady=5, sticky="ew")
        self.progress_bar.set(0)

        self.progress_status_var = tk.StringVar(value="Ready to Go")

        self.progress_status_label = ctk.CTkLabel(
            self.progress_container,
            textvariable=self.progress_status_var,
            font=self.btn_font_14,
        )
        self.progress_status_label.grid(row=0, column=1, padx=0, pady=5, sticky="ew")

        # --- Bottom Container (Row 3) ---
        self.bottom_container = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_container.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")

        self.bottom_container.grid_columnconfigure(0, weight=3)
        self.bottom_container.grid_columnconfigure(1, weight=3)
        self.bottom_container.grid_columnconfigure(2, weight=2)
        self.bottom_container.grid_columnconfigure(3, weight=2)
        self.bottom_container.grid_columnconfigure(4, weight=2)
        self.bottom_container.grid_columnconfigure(5, weight=2)

        self.start_btn = ctk.CTkButton(
            self.bottom_container,
            text="Folder Process",
            height=45,
            font=self.btn_font_15,
            command=self.start_process_threaded,
        )
        self.start_btn.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")

        self.start_btn.drop_target_register(DND_FILES)
        self.start_btn.dnd_bind("<<Drop>>", self.on_folder_drop)

        self.single_process_btn = ctk.CTkButton(
            self.bottom_container,
            text="File Process",
            height=45,
            fg_color="#e2700d",
            hover_color="#9c3f00",
            font=self.btn_font_16,
            command=self.start_single_process_threaded,
        )
        self.single_process_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.single_process_btn.drop_target_register(DND_FILES)
        self.single_process_btn.dnd_bind("<<Drop>>", self.on_file_drop)

        self.donate_button = ctk.CTkButton(
            self.bottom_container,
            text="Donate",
            height=45,
            image=self.heart_image,
            compound="right",
            fg_color="#FFD700",
            hover_color="#FFC400",
            text_color="#000000",
            font=self.btn_font_18,
            command=self.donate,
        )
        self.donate_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        self.import_btn = ctk.CTkButton(
            self.bottom_container,
            text="Import Settings",
            height=45,
            fg_color="#b434db",
            hover_color="#9b2bb8",
            text_color="#FFFFFF",
            font=self.btn_font_16,
            command=self.import_settings,
        )
        self.import_btn.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        self.export_btn = ctk.CTkButton(
            self.bottom_container,
            text="Export Settings",
            height=45,
            fg_color="#27ae60",
            hover_color="#186d3b",
            text_color="#FFFFFF",
            font=self.btn_font_16,
            command=self.export_settings,
        )
        self.export_btn.grid(row=0, column=4, padx=5, pady=5, sticky="ew")

        self.reset_button = ctk.CTkButton(
            self.bottom_container,
            text="Reset Settings",
            height=45,
            fg_color="#A9A9A9",
            hover_color="#808080",
            text_color="#000000",
            font=self.btn_font_16,
            command=self._reset_settings,
        )
        self.reset_button.grid(row=0, column=5, padx=(5, 0), pady=5, sticky="ew")

    def reset_progress_ui(self):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_status_var.set("Ready to Go")

    def start_convert_progress(self):
        self.after(0, self._start_convert_progress_ui)

    def _start_convert_progress_ui(self):
        self.progress_bar.configure(mode="indeterminate")
        self.progress_status_var.set("Converting Subtitles...")
        self.progress_bar.start()

    def start_processing_progress(self):
        self.after(0, self._start_processing_progress_ui)

    def _start_processing_progress_ui(self):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)

    def update_processing_progress(self, percent):
        self.after(0, lambda p=percent: self._update_processing_progress_ui(p))

    def _update_processing_progress_ui(self, percent):
        value = max(0.0, min(100.0, percent))
        self.progress_bar.set(value / 100.0)
        self.progress_status_var.set(f"Processing {value:.1f}%")

    def complete_progress(self):
        self.after(0, self._complete_progress_ui)

    def _complete_progress_ui(self):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(1)
        self.progress_status_var.set("100% Completed")

    def on_preprocess_dependency_toggle(self):
        """Enforce UTF-8 selection if any character conversion options are enabled."""
        if (
            self.chk_persian_question_mark_and_comma.get() == 1
            or self.chk_arabic_char.get() == 1
            or self.chk_arabic_num.get() == 1
            or self.chk_english_num.get() == 1
            or self.chk_space_to_invisible_space.get() == 1
            or self.chk_hexre_fixes.get() == 1
            or self.chk_force_rtl.get() == 1
            or self.chk_fix_abbreviations.get() == 1
            or self.chk_comma_fixes.get() == 1
            or self.chk_exclamation_fixes.get() == 1
            or self.chk_parentheses_fixes.get() == 1
            or self.chk_question_mark_fixes.get() == 1
            or self.chk_double_quotes_fixes.get() == 1
            or self.chk_dash_fixes.get() == 1
            or self.chk_comments_fixes.get() == 1
            or self.chk_dialog_hyphen_fix.get() == 1
            or self.chk_fix_misplaced_chars.get() == 1
        ):
            self.chk_encode_utf8.select()
        self.save_config()

    def on_utf8_toggle(self):
        """Disable character conversion features if UTF-8 is disabled since they require it."""
        if self.chk_encode_utf8.get() == 0:
            self.chk_persian_question_mark_and_comma.deselect()
            self.chk_arabic_char.deselect()
            self.chk_arabic_num.deselect()
            self.chk_english_num.deselect()
            self.chk_space_to_invisible_space.deselect()
            self.chk_hexre_fixes.deselect()
            self.chk_force_rtl.deselect()
            self.chk_fix_abbreviations.deselect()
            self.chk_comma_fixes.deselect()
            self.chk_exclamation_fixes.deselect()
            self.chk_parentheses_fixes.deselect()
            self.chk_question_mark_fixes.deselect()
            self.chk_double_quotes_fixes.deselect()
            self.chk_dash_fixes.deselect()
            self.chk_comments_fixes.deselect()
            self.chk_dialog_hyphen_fix.deselect()
            self.chk_fix_misplaced_chars.deselect()
        self.save_config()

    def on_reformat_dependency_toggle(self):
        """Enforce Reformat & Renumber selection if any linked post-process options are enabled."""
        if (
            self.chk_add_intro_credit.get() == 1
            or self.chk_remove_negative_timecodes.get() == 1
            or self.chk_remove_empty_subtitles.get() == 1
            or self.chk_fix_misplaced_timecodes.get() == 1
            or self.chk_remove_duplicate_subtitles.get() == 1
            or self.chk_fix_overlapping_timecodes.get() == 1
        ):
            self.chk_reformat_renumber.select()
        self.toggle_intro_credit_state()
        self.save_config()

    def on_reformat_renumber_toggle(self):
        """Disable linked post-process options if Reformat & Renumber is disabled."""
        if self.chk_reformat_renumber.get() == 0:
            self.chk_add_intro_credit.deselect()
            self.chk_remove_negative_timecodes.deselect()
            self.chk_remove_empty_subtitles.deselect()
            self.chk_fix_misplaced_timecodes.deselect()
            self.chk_remove_duplicate_subtitles.deselect()
            self.chk_fix_overlapping_timecodes.deselect()
        self.toggle_intro_credit_state()
        self.save_config()

    def toggle_intro_credit_state(self):
        """Enable or disable intro credit duration and listbox widgets based on checkbox state."""
        if self.chk_add_intro_credit.get() == 1:
            self.opt_intro_credit_duration.configure(state="normal")
            self.lst_intro_credit.set_state(True)
        else:
            self.opt_intro_credit_duration.configure(state="disabled")
            self.lst_intro_credit.set_state(False)

    # --- Widget Toggles ---
    def toggle_bypass(self):
        is_on = self.chk_bypass.get() == 1
        self.lst_bypass.set_state(is_on)
        self.save_config()

    def toggle_remove(self):
        is_on = self.chk_remove.get() == 1
        self.lst_remove.set_state(is_on)
        self.save_config()

    def toggle_replace(self):
        is_on = self.chk_replace.get() == 1
        self.lst_replace.set_state(is_on)
        self.save_config()

    def resource_path(self, relative_path):
        temp_dir = os.path.dirname(__file__)
        return os.path.join(temp_dir, relative_path)

    def on_close(self):
        """
        Handles application shutdown, cleans up the lock file, saves config,
        and checks if a process is running before exiting.
        """
        self.write_log("Application closing.")
        self.save_config()
        self.lock.release()
        self.destroy()

    # --- Config Management Methods ---
    def load_config(self):
        config = self.config_manager.load()

        w = int(config.get("window_width", 800))
        h = int(config.get("window_height", 600))

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = int((screen_width / 2) - (w / 2))
        y = int((screen_height / 2) - (h / 2))

        self.geometry(f"{w}x{h}+{x}+{y}")

        if config.get("is_maximized", 0) == 1:
            self.after(200, lambda: self.state("zoomed"))
        else:
            self.after(200, lambda: self.state("normal"))

        folder_path = config.get("folder_path", "")
        self._update_path_entry(folder_path)

        theme_mode = config.get("theme_mode", 1)
        if theme_mode == 1:
            self.theme_switch.select()
            ctk.set_appearance_mode("dark")
        else:
            self.theme_switch.deselect()
            ctk.set_appearance_mode("light")

        save_logs = config.get("save_logs", 0)
        if self.log_switch.cget("state") == "normal":
            if save_logs == 1:
                self.log_switch.select()
            else:
                self.log_switch.deselect()
        else:
            self.log_switch.deselect()

        if config.get("remove_alignment_tags", 1) == 1:
            self.chk_remove_alignment_tags.select()
        else:
            self.chk_remove_alignment_tags.deselect()

        if config.get("trim_spaces", 1) == 1:
            self.chk_trim_spaces.select()
        else:
            self.chk_trim_spaces.deselect()

        if config.get("remove_unneeded_spaces", 1) == 1:
            self.chk_remove_unneeded_spaces.select()
        else:
            self.chk_remove_unneeded_spaces.deselect()

        if config.get("fix_abbreviations", 1) == 1:
            self.chk_fix_abbreviations.select()
        else:
            self.chk_fix_abbreviations.deselect()

        if config.get("comma_fixes", 1) == 1:
            self.chk_comma_fixes.select()
        else:
            self.chk_comma_fixes.deselect()

        if config.get("exclamation_fixes", 1) == 1:
            self.chk_exclamation_fixes.select()
        else:
            self.chk_exclamation_fixes.deselect()

        if config.get("parentheses_fixes", 1) == 1:
            self.chk_parentheses_fixes.select()
        else:
            self.chk_parentheses_fixes.deselect()

        if config.get("question_mark_fixes", 1) == 1:
            self.chk_question_mark_fixes.select()
        else:
            self.chk_question_mark_fixes.deselect()

        if config.get("double_quotes_fixes", 1) == 1:
            self.chk_double_quotes_fixes.select()
        else:
            self.chk_double_quotes_fixes.deselect()

        if config.get("dash_fixes", 1) == 1:
            self.chk_dash_fixes.select()
        else:
            self.chk_dash_fixes.deselect()

        if config.get("comments_fixes", 1) == 1:
            self.chk_comments_fixes.select()
        else:
            self.chk_comments_fixes.deselect()

        if config.get("dialog_hyphen_fix", 1) == 1:
            self.chk_dialog_hyphen_fix.select()
        else:
            self.chk_dialog_hyphen_fix.deselect()

        if config.get("fix_misplaced_chars", 1) == 1:
            self.chk_fix_misplaced_chars.select()
        else:
            self.chk_fix_misplaced_chars.deselect()

        if config.get("remove_standalone_dots", 1) == 1:
            self.chk_remove_standalone_dots.select()
        else:
            self.chk_remove_standalone_dots.deselect()

        if config.get("persian_question_mark_and_comma", 1) == 1:
            self.chk_persian_question_mark_and_comma.select()
        else:
            self.chk_persian_question_mark_and_comma.deselect()

        if config.get("arabic_char_to_persian", 1) == 1:
            self.chk_arabic_char.select()
        else:
            self.chk_arabic_char.deselect()

        if config.get("arabic_num_to_persian", 1) == 1:
            self.chk_arabic_num.select()
        else:
            self.chk_arabic_num.deselect()

        if config.get("english_num_to_persian", 1) == 1:
            self.chk_english_num.select()
        else:
            self.chk_english_num.deselect()

        if config.get("space_to_invisible_space", 1):
            self.chk_space_to_invisible_space.select()
        else:
            self.chk_space_to_invisible_space.deselect()

        if config.get("hexre_fixes", 1) == 1:
            self.chk_hexre_fixes.select()
        else:
            self.chk_hexre_fixes.deselect()

        if config.get("add_missing_spaces", 1) == 1:
            self.chk_add_missing_spaces.select()
        else:
            self.chk_add_missing_spaces.deselect()

        # Process Tab Loading
        bypass_enabled = config.get("bypass_enabled", 1) == 1
        if bypass_enabled:
            self.chk_bypass.select()
        else:
            self.chk_bypass.deselect()
        self.lst_bypass.set_items_from_text(config.get("bypass_list", ""))
        self.lst_bypass.set_state(bypass_enabled)

        remove_enabled = config.get("remove_enabled", 1) == 1
        if remove_enabled:
            self.chk_remove.select()
        else:
            self.chk_remove.deselect()
        self.lst_remove.set_items_from_text(config.get("remove_list", ""))
        self.lst_remove.set_state(remove_enabled)

        replace_enabled = config.get("replace_enabled", 1) == 1
        if replace_enabled:
            self.chk_replace.select()
        else:
            self.chk_replace.deselect()
        self.lst_replace.set_items_from_text(config.get("replace_list", ""))
        self.lst_replace.set_state(replace_enabled)

        # Post-Process Tab Loading
        if config.get("post_trim_spaces", 1) == 1:
            self.chk_post_trim_spaces.select()
        else:
            self.chk_post_trim_spaces.deselect()

        if config.get("remove_empty_tags", 1) == 1:
            self.chk_remove_empty_tags.select()
        else:
            self.chk_remove_empty_tags.deselect()

        if config.get("add_intro_credit", 0) == 1:
            self.chk_add_intro_credit.select()
        else:
            self.chk_add_intro_credit.deselect()

        dur_val = str(config.get("intro_credit_duration", "8"))
        if dur_val in ["2", "3", "4", "5", "6", "7", "8", "9", "10"]:
            self.opt_intro_credit_duration.set(dur_val)
        else:
            self.opt_intro_credit_duration.set("8")

        self.lst_intro_credit.set_items_from_text(config.get("intro_credit_text", ""))

        if config.get("force_rtl", 1) == 1:
            self.chk_force_rtl.select()
        else:
            self.chk_force_rtl.deselect()

        if config.get("remove_negative_timecodes", 1) == 1:
            self.chk_remove_negative_timecodes.select()
        else:
            self.chk_remove_negative_timecodes.deselect()

        if config.get("fix_misplaced_timecodes", 1) == 1:
            self.chk_fix_misplaced_timecodes.select()
        else:
            self.chk_fix_misplaced_timecodes.deselect()

        if config.get("remove_duplicate_subtitles", 1) == 1:
            self.chk_remove_duplicate_subtitles.select()
        else:
            self.chk_remove_duplicate_subtitles.deselect()

        if config.get("fix_overlapping_timecodes", 1) == 1:
            self.chk_fix_overlapping_timecodes.select()
        else:
            self.chk_fix_overlapping_timecodes.deselect()

        if config.get("remove_empty_subtitles", 1) == 1:
            self.chk_remove_empty_subtitles.select()
        else:
            self.chk_remove_empty_subtitles.deselect()

        if config.get("reformat_renumber", 1) == 1:
            self.chk_reformat_renumber.select()
        else:
            self.chk_reformat_renumber.deselect()

        if config.get("encode_utf8", 1) == 1:
            self.chk_encode_utf8.select()
        else:
            self.chk_encode_utf8.deselect()

        # Extra Options Loading
        if config.get("delete_original", 0) == 1:
            self.chk_delete_original.select()
        else:
            self.chk_delete_original.deselect()

        if config.get("detailed_subtitle_logs", 1) == 1:
            self.chk_detailed_logs.select()
        else:
            self.chk_detailed_logs.deselect()

        if config.get("enable_dnd", 1) == 1:
            self.chk_enable_dnd.select()
        else:
            self.chk_enable_dnd.deselect()

        if config.get("convert_ass_comments", 0) == 1:
            self.chk_convert_ass_comments.select()
        else:
            self.chk_convert_ass_comments.deselect()

        if config.get("delete_converted_temp_files", 0) == 1:
            self.chk_delete_converted_temp_files.select()
        else:
            self.chk_delete_converted_temp_files.deselect()

        self.toggle_intro_credit_state()

        # Force synchronous theme palette refresh across all listbox managers
        self.lst_bypass.apply_theme()
        self.lst_remove.apply_theme()
        self.lst_replace.apply_theme()
        self.lst_intro_credit.apply_theme()

        sys_info = Logger.get_system_info()
        self.write_log(f"System Info: {sys_info}")
        self.write_log("Application config loaded/reloaded.")

    def save_config(self):
        self.start_btn.focus_set()
        self.update_idletasks()
        self.update()

        try:
            is_max = 1 if self.state() == "zoomed" else 0
        except Exception:
            is_max = 0

        current_width = self.winfo_width()
        current_height = self.winfo_height()

        if is_max == 1 or current_width < 100 or current_height < 100:
            loaded_config = self.config_manager.load()
            current_width = int(loaded_config.get("window_width", 800))
            current_height = int(loaded_config.get("window_height", 600))

        config_data = {
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "folder_path": self.path_entry.get(),
            "theme_mode": self.theme_switch.get(),
            "window_width": current_width,
            "window_height": current_height,
            "is_maximized": is_max,
            "save_logs": self.log_switch.get(),
            "remove_alignment_tags": self.chk_remove_alignment_tags.get(),
            "trim_spaces": self.chk_trim_spaces.get(),
            "remove_unneeded_spaces": self.chk_remove_unneeded_spaces.get(),
            "fix_abbreviations": self.chk_fix_abbreviations.get(),
            "comma_fixes": self.chk_comma_fixes.get(),
            "exclamation_fixes": self.chk_exclamation_fixes.get(),
            "parentheses_fixes": self.chk_parentheses_fixes.get(),
            "question_mark_fixes": self.chk_question_mark_fixes.get(),
            "double_quotes_fixes": self.chk_double_quotes_fixes.get(),
            "dash_fixes": self.chk_dash_fixes.get(),
            "comments_fixes": self.chk_comments_fixes.get(),
            "dialog_hyphen_fix": self.chk_dialog_hyphen_fix.get(),
            "fix_misplaced_chars": self.chk_fix_misplaced_chars.get(),
            "remove_standalone_dots": self.chk_remove_standalone_dots.get(),
            "persian_question_mark_and_comma": self.chk_persian_question_mark_and_comma.get(),
            "arabic_char_to_persian": self.chk_arabic_char.get(),
            "arabic_num_to_persian": self.chk_arabic_num.get(),
            "english_num_to_persian": self.chk_english_num.get(),
            "space_to_invisible_space": self.chk_space_to_invisible_space.get(),
            "hexre_fixes": self.chk_hexre_fixes.get(),
            "add_missing_spaces": self.chk_add_missing_spaces.get(),
            "bypass_enabled": self.chk_bypass.get(),
            "bypass_list": self.lst_bypass.get_items_text(),
            "remove_enabled": self.chk_remove.get(),
            "remove_list": self.lst_remove.get_items_text(),
            "replace_enabled": self.chk_replace.get(),
            "replace_list": self.lst_replace.get_items_text(),
            "post_trim_spaces": self.chk_post_trim_spaces.get(),
            "remove_empty_tags": self.chk_remove_empty_tags.get(),
            "add_intro_credit": self.chk_add_intro_credit.get(),
            "intro_credit_duration": self.opt_intro_credit_duration.get(),
            "intro_credit_text": self.lst_intro_credit.get_items_text(),
            "force_rtl": self.chk_force_rtl.get(),
            "remove_negative_timecodes": self.chk_remove_negative_timecodes.get(),
            "fix_misplaced_timecodes": self.chk_fix_misplaced_timecodes.get(),
            "remove_duplicate_subtitles": self.chk_remove_duplicate_subtitles.get(),
            "fix_overlapping_timecodes": self.chk_fix_overlapping_timecodes.get(),
            "remove_empty_subtitles": self.chk_remove_empty_subtitles.get(),
            "reformat_renumber": self.chk_reformat_renumber.get(),
            "encode_utf8": self.chk_encode_utf8.get(),
            "delete_original": self.chk_delete_original.get(),
            "detailed_subtitle_logs": self.chk_detailed_logs.get(),
            "enable_dnd": self.chk_enable_dnd.get(),
            "convert_ass_comments": self.chk_convert_ass_comments.get(),
            "delete_converted_temp_files": self.chk_delete_converted_temp_files.get(),
        }
        self.config_manager.save(config_data)
        self.write_log("Config saved.")

    def _update_path_entry(self, path):
        self.path_entry.configure(state="normal")
        self.path_entry.delete(0, "end")

        if path and os.path.isdir(path):
            self.path_entry.insert(0, path)
            self.log_switch.configure(state="normal")
        else:
            self.path_entry.configure(placeholder_text="Select Source Folder Which Contains Subtitles")
            self.log_switch.deselect()
            self.log_switch.configure(state="disabled")

        self.path_entry.configure(state="readonly")

    def _apply_default_config(self):
        self._update_path_entry("")
        self.theme_switch.select()
        ctk.set_appearance_mode("dark")

        try:
            self.state("normal")
        except Exception:
            pass

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width / 2) - (800 / 2))
        y = int((screen_height / 2) - (600 / 2))
        self.geometry(f"800x600+{x}+{y}")

        self.log_switch.deselect()
        self.log_switch.configure(state="disabled")

        self.chk_remove_alignment_tags.select()
        self.chk_trim_spaces.select()
        self.chk_remove_unneeded_spaces.select()
        self.chk_fix_abbreviations.select()
        self.chk_comma_fixes.select()
        self.chk_exclamation_fixes.select()
        self.chk_parentheses_fixes.select()
        self.chk_question_mark_fixes.select()
        self.chk_remove_standalone_dots.select()
        self.chk_persian_question_mark_and_comma.select()
        self.chk_arabic_char.select()
        self.chk_arabic_num.select()
        self.chk_english_num.select()
        self.chk_space_to_invisible_space.select()
        self.chk_hexre_fixes.select()
        self.chk_add_missing_spaces.select()
        self.chk_fix_misplaced_chars.select()

        self.chk_bypass.select()
        self.lst_bypass.set_items([])
        self.lst_bypass.set_state(True)

        self.chk_remove.select()
        self.lst_remove.set_items([])
        self.lst_remove.set_state(True)

        self.chk_replace.select()
        self.lst_replace.set_items([])
        self.lst_replace.set_state(True)

        self.chk_post_trim_spaces.select()
        self.chk_remove_empty_tags.select()
        self.chk_add_intro_credit.deselect()
        self.opt_intro_credit_duration.set("8")
        self.lst_intro_credit.set_items([])
        self.lst_intro_credit.set_state(False)

        self.chk_force_rtl.select()
        self.chk_remove_negative_timecodes.select()
        self.chk_fix_misplaced_timecodes.select()
        self.chk_remove_duplicate_subtitles.select()
        self.chk_fix_overlapping_timecodes.select()
        self.chk_remove_empty_subtitles.select()
        self.chk_reformat_renumber.select()
        self.chk_encode_utf8.select()
        self.chk_delete_original.deselect()
        self.chk_detailed_logs.select()

        self.chk_enable_dnd.select()
        self.chk_convert_ass_comments.deselect()
        self.chk_delete_converted_temp_files.deselect()

        self.toggle_intro_credit_state()

        self.lst_bypass.apply_theme()
        self.lst_remove.apply_theme()
        self.lst_replace.apply_theme()
        self.lst_intro_credit.apply_theme()

    def import_settings(self):
        file_path = filedialog.askopenfilename(title="Select Configuration File", filetypes=[("JSON files", "*.json")])

        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                imported_config = json.load(f)

            if imported_config.get("app_name") != APP_NAME:
                messagebox.showerror("Error", "Invalid configuration file for this application.")
                return

            excluded_keys = ["app_name", "app_version"]
            current_config = self.config_manager.load()

            updated_count = 0
            for key, value in imported_config.items():
                if key in current_config and key not in excluded_keys:
                    current_config[key] = value
                    updated_count += 1

            if updated_count > 0:
                self.config_manager.save(current_config)
                self.load_config()
                self.write_log(f"Settings imported successfully from: {file_path}")
                messagebox.showinfo("Success", "Settings have been imported and applied successfully.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to import settings: \n\n{str(e)}")

    def export_settings(self):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
        default_filename = f"PST-{timestamp}.json"

        file_path = filedialog.asksaveasfilename(
            title="Export Settings",
            initialfile=default_filename,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
        )

        if not file_path:
            return

        try:
            self.save_config()
            config_data = self.config_manager.load()

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)

            self.write_log(f"Settings exported successfully to: {file_path}")
            messagebox.showinfo("Success", f"Settings exported to:\n\n{file_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export settings: \n\n{str(e)}")

    def _reset_settings(self):
        self.write_log("Settings reset to default.")
        self._apply_default_config()
        self.save_config()
        messagebox.showinfo("Settings Reset", "All settings have been reset to default values.")

    def browse_folder(self):
        initial_dir = (
            self.path_entry.get() if os.path.isdir(self.path_entry.get()) else os.path.expanduser("~/Documents")
        )
        folder_selected = filedialog.askdirectory(
            initialdir=initial_dir, title="Select Source Folder Which Contains Subtitles"
        )

        if folder_selected:
            self.write_log(f"Target folder changing to: {folder_selected}")
            self._update_path_entry(folder_selected)
            self.write_log("Target folder successfully changed.")

    def write_log(self, message):
        folder = self.path_entry.get()
        is_enabled = self.log_switch.get() == 1
        Logger.log(message, folder, is_enabled)

    def toggle_logs(self):
        current_state = self.log_switch.get() == 1
        if current_state:
            messagebox.showinfo("Logs Enabled", "Logs will be saved in the selected folder under /Logs directory.")
            Logger.log("Logging enabled by user.", self.path_entry.get(), True)
        else:
            Logger.log("Logging disabled by user.", self.path_entry.get(), True)
        self.save_config()

    def change_theme(self):
        mode = "dark" if self.theme_switch.get() == 1 else "light"
        ctk.set_appearance_mode(mode)
        self.write_log(f"Appearance mode changed to {mode}")
        self.lst_bypass.apply_theme()
        self.lst_remove.apply_theme()
        self.lst_replace.apply_theme()
        self.lst_intro_credit.apply_theme()
        self.save_config()

    def _run_processing_pipeline(self, processor, is_single_file=False):
        processor.run()
        successful = getattr(processor, "successful_count", 0)
        failed = getattr(processor, "failed_count", 0)
        discovered = getattr(processor, "total_files_discovered", successful + failed)
        total = min(discovered, successful + failed)
        elapsed = getattr(processor, "elapsed_time", 0)
        lines_proc = getattr(processor, "total_lines_processed", 0)
        lines_per_sec = lines_proc / elapsed if elapsed > 0 else 0

        if not is_single_file:
            summary_message = (
                f"Subtitle processing has completed.\n\n"
                f"Processed {lines_proc} lines in {elapsed:.2f} seconds ({lines_per_sec:.2f} lines/sec).\n\n"
                f"Total files discovered: {discovered}\n"
                f"Successfully processed: {successful}\n"
                f"Failed / Skipped: {failed}\n\n"
                f'Output files are located in the "Outputs" folder within the selected directory.'
            )
        else:
            summary_message = (
                f"Single file processing has completed.\n\n"
                f"Processed {lines_proc} lines in {elapsed:.2f} seconds ({lines_per_sec:.2f} lines/sec).\n\n"
                f"Total files selected: {discovered}\n"
                f"Successfully processed: {successful}\n"
                f"Failed / Skipped: {failed}\n\n"
                f"Output files and logs are located in the respective file directories."
            )

        def finish():
            if failed > 0:
                messagebox.showwarning(
                    "Process Completed with Warnings",
                    summary_message,
                )
            else:
                messagebox.showinfo(
                    "Process Completed",
                    summary_message,
                )
            self.after(250, self.reset_progress_ui)
            self.attributes("-disabled", False)
            self.lift()
            self.focus_force()

        self.after(0, finish)

    def _get_run_options(self):
        return {
            "remove_alignment_tags": self.chk_remove_alignment_tags.get(),
            "trim_spaces": self.chk_trim_spaces.get(),
            "remove_unneeded_spaces": self.chk_remove_unneeded_spaces.get(),
            "fix_abbreviations": self.chk_fix_abbreviations.get(),
            "comma_fixes": self.chk_comma_fixes.get(),
            "exclamation_fixes": self.chk_exclamation_fixes.get(),
            "parentheses_fixes": self.chk_parentheses_fixes.get(),
            "question_mark_fixes": self.chk_question_mark_fixes.get(),
            "double_quotes_fixes": self.chk_double_quotes_fixes.get(),
            "dash_fixes": self.chk_dash_fixes.get(),
            "comments_fixes": self.chk_comments_fixes.get(),
            "dialog_hyphen_fix": self.chk_dialog_hyphen_fix.get(),
            "fix_misplaced_chars": self.chk_fix_misplaced_chars.get(),
            "remove_standalone_dots": self.chk_remove_standalone_dots.get(),
            "persian_question_mark_and_comma": self.chk_persian_question_mark_and_comma.get(),
            "arabic_char_to_persian": self.chk_arabic_char.get(),
            "arabic_num_to_persian": self.chk_arabic_num.get(),
            "english_num_to_persian": self.chk_english_num.get(),
            "space_to_invisible_space": self.chk_space_to_invisible_space.get(),
            "hexre_fixes": self.chk_hexre_fixes.get(),
            "add_missing_spaces": self.chk_add_missing_spaces.get(),
            "bypass_enabled": self.chk_bypass.get(),
            "bypass_list": self.lst_bypass.get_items_text(),
            "remove_enabled": self.chk_remove.get(),
            "remove_list": self.lst_remove.get_items_text(),
            "replace_enabled": self.chk_replace.get(),
            "replace_list": self.lst_replace.get_items_text(),
            "post_trim_spaces": self.chk_post_trim_spaces.get(),
            "remove_empty_tags": self.chk_remove_empty_tags.get(),
            "add_intro_credit": self.chk_add_intro_credit.get(),
            "intro_credit_duration": self.opt_intro_credit_duration.get(),
            "intro_credit_text": self.lst_intro_credit.get_items_text(),
            "force_rtl": self.chk_force_rtl.get(),
            "remove_negative_timecodes": self.chk_remove_negative_timecodes.get(),
            "fix_misplaced_timecodes": self.chk_fix_misplaced_timecodes.get(),
            "remove_duplicate_subtitles": self.chk_remove_duplicate_subtitles.get(),
            "fix_overlapping_timecodes": self.chk_fix_overlapping_timecodes.get(),
            "remove_empty_subtitles": self.chk_remove_empty_subtitles.get(),
            "reformat_renumber": self.chk_reformat_renumber.get(),
            "encode_utf8": self.chk_encode_utf8.get(),
            "delete_original": self.chk_delete_original.get(),
            "detailed_subtitle_logs": self.chk_detailed_logs.get(),
            "enable_dnd": self.chk_enable_dnd.get(),
            "convert_ass_comments": self.chk_convert_ass_comments.get(),
            "delete_converted_temp_files": self.chk_delete_converted_temp_files.get(),
        }

    def start_process_threaded(self):
        threading.Thread(target=self.start_process, daemon=True).start()

    def start_process(self):
        current_path = self.path_entry.get()
        if not current_path:
            messagebox.showwarning("Error", "Please select a folder first.")
            return

        self.attributes("-disabled", True)
        self.reset_progress_ui()
        self.save_config()

        run_options = self._get_run_options()

        processor = SubtitleProcessor(
            current_path,
            options=run_options,
            progress_callback=self.update_processing_progress,
            convert_start_callback=self.start_convert_progress,
            process_start_callback=self.start_processing_progress,
            complete_callback=self.complete_progress,
        )
        self._run_processing_pipeline(processor, is_single_file=False)

    def start_single_process_threaded(self):
        threading.Thread(target=self.start_single_process, daemon=True).start()

    def start_single_process(self):
        selected_files = filedialog.askopenfilenames(
            title="Select Subtitle Files", filetypes=[("Subtitle Files", "*.srt *.txt *.vtt *.ass")]
        )

        if not selected_files:
            return

        count = len(selected_files)
        confirm = messagebox.askyesno(
            "Confirm Process", f"Do you want to process {count} selected file(s) with the current settings?"
        )

        if not confirm:
            return

        self.attributes("-disabled", True)
        self.reset_progress_ui()
        self.save_config()

        run_options = self._get_run_options()

        processor = SubtitleProcessor(
            "",
            options=run_options,
            target_files=selected_files,
            progress_callback=self.update_processing_progress,
            convert_start_callback=self.start_convert_progress,
            process_start_callback=self.start_processing_progress,
            complete_callback=self.complete_progress,
        )
        self._run_processing_pipeline(processor, is_single_file=True)

    def on_folder_drop(self, event):
        if self.chk_enable_dnd.get() == 0:
            return

        paths = self.tk.splitlist(event.data)

        valid_folders = []
        invalid_items = []

        for path in paths:
            if os.path.isdir(path):
                valid_folders.append(path)
            else:
                invalid_items.append(path)

        if not valid_folders:
            messagebox.showerror(
                "Invalid Drop", "No valid folders were dropped.\nPlease drop only folders on this button."
            )
            return

        if invalid_items:
            messagebox.showwarning(
                "Warning", "Some dropped items were ignored.\nFiles are not supported here, please drop folders only."
            )

        folder_to_process = valid_folders[0]

        confirm = messagebox.askyesno(
            "Confirm Process",
            f"Do you want to process the dropped folder with the current settings?\n\nFolder: {folder_to_process}",
        )

        if not confirm:
            return

        self.attributes("-disabled", True)
        self.save_config()

        run_options = self._get_run_options()
        self.reset_progress_ui()
        processor = SubtitleProcessor(
            folder_to_process,
            options=run_options,
            progress_callback=self.update_processing_progress,
            convert_start_callback=self.start_convert_progress,
            process_start_callback=self.start_processing_progress,
            complete_callback=self.complete_progress,
        )

        threading.Thread(target=self._run_processing_pipeline, args=(processor, False), daemon=True).start()

    def on_file_drop(self, event):
        if self.chk_enable_dnd.get() == 0:
            return

        paths = self.tk.splitlist(event.data)

        valid_files = []
        invalid_files = []

        for path in paths:
            if os.path.isfile(path) and path.lower().endswith((".srt", ".txt", ".vtt", ".ass")):
                valid_files.append(path)
            else:
                invalid_files.append(path)

        if not valid_files:
            messagebox.showerror(
                "Invalid Drop",
                'No valid subtitle files were dropped.\nPlease drop only ".srt", ".txt", ".vtt", or ".ass" files.',
            )
            return

        if invalid_files:
            messagebox.showwarning(
                "Warning", "Some dropped items were ignored.\nFolders or unsupported file extensions are not supported."
            )

        confirm = messagebox.askyesno(
            "Confirm Process",
            f"Do you want to process {len(valid_files)} dropped file(s) with the current settings?",
        )

        if not confirm:
            return

        self.attributes("-disabled", True)
        self.save_config()

        run_options = self._get_run_options()
        self.reset_progress_ui()
        processor = SubtitleProcessor(
            "",
            options=run_options,
            target_files=valid_files,
            progress_callback=self.update_processing_progress,
            convert_start_callback=self.start_convert_progress,
            process_start_callback=self.start_processing_progress,
            complete_callback=self.complete_progress,
        )

        threading.Thread(target=self._run_processing_pipeline, args=(processor, True), daemon=True).start()

    def donate(self):
        """Opens a donation window with options to support the project."""
        top = ctk.CTkToplevel(self)
        top.title("Donate ❤")
        top.resizable(False, False)
        self.attributes("-disabled", True)

        def top_on_close():
            self.attributes("-disabled", False)
            top.destroy()
            self.lift()
            self.focus()

        top.protocol("WM_DELETE_WINDOW", top_on_close)
        top.withdraw()

        if self.heart_icon:
            top.after(250, lambda: top.iconphoto(False, self.heart_icon))

        width = 500
        height = 300
        x = (top.winfo_screenwidth() // 2) - (width // 2)
        y = (top.winfo_screenheight() // 2) - (height // 2)
        top.geometry(f"{width}x{height}+{x}+{y}")

        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=0)

        try:
            image_path = self.resource_path(os.path.join("assets", "donate.png"))
            img = Image.open(image_path)
            width_img, height_img = img.size
            donate_img = ctk.CTkImage(
                light_image=Image.open(image_path), dark_image=Image.open(image_path), size=(width_img, height_img)
            )
            donate_button = ctk.CTkLabel(top, image=donate_img, text="", cursor="hand2")
            donate_button.grid(row=0, column=0, columnspan=2, pady=(30, 20))
        except Exception:
            donate_button = ctk.CTkLabel(top, text="Support the Developer!", font=("Segoe UI", 16, "bold"))
            donate_button.grid(row=0, column=0, columnspan=2, pady=(30, 20))

        def open_link(event=None):
            webbrowser.open_new("http://www.coffeete.ir/Titan")

        donate_button.bind("<Button-1>", open_link)

        usdt_label = ctk.CTkLabel(top, text="USDT (Tether) – TRC20 Wallet Address :", font=("Segoe UI", 14, "bold"))
        usdt_label.grid(row=1, column=0, columnspan=2, pady=(30, 5), sticky="w", padx=20)

        wallet_address = "TGoKk5zD3BMSGbmzHnD19m9YLpH5ZP8nQe"
        wallet_entry = ctk.CTkEntry(top, width=300)
        wallet_entry.insert(0, wallet_address)
        wallet_entry.configure(state="readonly")
        wallet_entry.grid(row=2, column=0, padx=(20, 10), pady=5, sticky="ew")

        copy_btn = ctk.CTkButton(top, text="Copy", width=80)
        copy_btn.grid(row=2, column=1, padx=(0, 20), pady=5, sticky="w")

        tooltip = None

        def copy_wallet():
            nonlocal tooltip
            self.clipboard_clear()
            self.clipboard_append(wallet_address)
            self.update()

            if tooltip:
                tooltip.hidetip()
                tooltip = None

            tooltip = Hovertip(copy_btn, "Copied to clipboard!")
            tooltip.showtip()

            def hide_tip():
                if tooltip:
                    tooltip.hidetip()

            top.after(2000, hide_tip)

        copy_btn.configure(command=copy_wallet)
        top.after(200, top.deiconify)


if __name__ == "__main__":
    app = PersianSubtitleToolkit()
    app.mainloop()
