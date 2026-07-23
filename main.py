from core import *
import customtkinter as ctk
from customtkinter import filedialog
import tkinter as tk
from tkinter import messagebox
from PIL import ImageTk, Image
from idlelib.tooltip import Hovertip
import webbrowser
import arabic_reshaper
from bidi.algorithm import get_display


def check_and_apply_rtl(widget):
    """Configure RTL/LTR text alignment and fix word inversion based on Persian character detection."""
    # Using specific tags with formatting to force correct word ordering (Bidi layout)
    widget.tag_configure("rtl", justify="right")
    widget.tag_configure("ltr", justify="left")

    # Clear existing orientation tags before reapplying to prevent conflicts
    widget.tag_remove("rtl", "1.0", "end")
    widget.tag_remove("ltr", "1.0", "end")

    text = widget.get("1.0", "end-1c")
    if any("\u0600" <= c <= "\u06ff" for c in text):
        widget.tag_add("rtl", "1.0", "end")
    else:
        widget.tag_add("ltr", "1.0", "end")


def textbox_undo(textbox):
    """Perform undo action on the textbox."""
    try:
        textbox._textbox.edit_undo()
        check_and_apply_rtl(textbox._textbox)
    except tk.TclError:
        pass


def textbox_redo(textbox):
    """Perform redo action on the textbox."""
    try:
        textbox._textbox.edit_redo()
        check_and_apply_rtl(textbox._textbox)
    except tk.TclError:
        pass


def textbox_cut(textbox):
    """Perform cut action on the textbox."""
    try:
        if textbox._textbox.tag_ranges("sel"):
            textbox_copy(textbox)
            textbox._textbox.delete("sel.first", "sel.last")
            check_and_apply_rtl(textbox._textbox)
    except tk.TclError:
        pass


def textbox_copy(textbox):
    """Perform copy action on the textbox."""
    try:
        if textbox._textbox.tag_ranges("sel"):
            text = textbox._textbox.get("sel.first", "sel.last")
            textbox.clipboard_clear()
            textbox.clipboard_append(text)
    except tk.TclError:
        pass


def textbox_paste(textbox):
    """Perform paste action on the textbox."""
    try:
        text = textbox.clipboard_get()
        if textbox._textbox.tag_ranges("sel"):
            textbox._textbox.delete("sel.first", "sel.last")
        textbox._textbox.insert("insert", text)
        check_and_apply_rtl(textbox._textbox)
    except tk.TclError:
        pass


def textbox_delete_selection(textbox):
    """Perform delete action on the selection."""
    try:
        if textbox._textbox.tag_ranges("sel"):
            textbox._textbox.delete("sel.first", "sel.last")
        check_and_apply_rtl(textbox._textbox)
    except tk.TclError:
        pass


def textbox_select_all(textbox):
    """Select all text in the textbox."""
    widget = textbox._textbox
    widget.tag_add("sel", "1.0", "end-1c")
    widget.mark_set("insert", "1.0")
    widget.see("insert")
    widget.focus_set()
    return "break"


def reshape_persian_text(text):
    lines = text.split("\n")
    result = []

    for line in lines:
        if any("\u0600" <= c <= "\u06ff" for c in line):
            result.append(get_display(arabic_reshaper.reshape(line)))
        else:
            result.append(line)

    return "\n".join(result)


def textbox_focus_in(textbox):
    if hasattr(textbox, "_original_text"):
        textbox.delete("1.0", "end")
        textbox.insert("1.0", textbox._original_text)

        widget = textbox._textbox

        widget.tag_remove("rtl", "1.0", "end")
        widget.tag_remove("ltr", "1.0", "end")

        check_and_apply_rtl(widget)


def textbox_focus_out(textbox):
    original_text = textbox.get("1.0", "end-1c")

    textbox._original_text = original_text

    display_text = reshape_persian_text(original_text)

    textbox.delete("1.0", "end")
    textbox.insert("1.0", display_text)

    widget = textbox._textbox

    widget.tag_remove("rtl", "1.0", "end")
    widget.tag_remove("ltr", "1.0", "end")

    if any("\u0600" <= c <= "\u06ff" for c in original_text):
        widget.tag_configure("rtl", justify="right")
        widget.tag_add("rtl", "1.0", "end")
    else:
        widget.tag_configure("ltr", justify="left")
        widget.tag_add("ltr", "1.0", "end")


def setup_enhanced_textbox(textbox):
    textbox._textbox.configure(undo=True)

    menu = tk.Menu(textbox, tearoff=0)

    menu.add_command(label="Undo\t\t", accelerator="Ctrl+Z", command=lambda: textbox_undo(textbox))
    menu.add_command(label="Redo\t\t", accelerator="Ctrl+Y", command=lambda: textbox_redo(textbox))
    menu.add_separator()
    menu.add_command(label="Cut\t\t", accelerator="Ctrl+X", command=lambda: textbox_cut(textbox))
    menu.add_command(label="Copy\t\t", accelerator="Ctrl+C", command=lambda: textbox_copy(textbox))
    menu.add_command(label="Paste\t\t", accelerator="Ctrl+V", command=lambda: textbox_paste(textbox))
    menu.add_command(label="Delete\t\t", accelerator="Delete", command=lambda: textbox_delete_selection(textbox))
    menu.add_separator()
    menu.add_command(label="Select All\t\t", accelerator="Ctrl+A", command=lambda: textbox_select_all(textbox))

    def show_menu(event):
        menu.tk_popup(event.x_root, event.y_root)

    widget = textbox._textbox
    textbox._original_text = ""

    def textbox_mouse_leave(textbox):
        current_focus = textbox.focus_get()

        if current_focus == textbox or current_focus == textbox._textbox:
            return

        try:
            if textbox._textbox.tag_ranges("sel"):
                return
        except Exception:
            pass

        textbox.master.focus_set()

    widget.bind(
        "<FocusIn>",
        lambda event, tb=textbox: textbox_focus_in(tb),
        add="+",
    )

    widget.bind(
        "<FocusOut>",
        lambda event, tb=textbox: textbox_focus_out(tb),
        add="+",
    )

    widget.bind(
        "<Leave>",
        lambda event, tb=textbox: textbox_mouse_leave(tb),
        add="+",
    )
    # Force right-to-left typing behavior for Persian text
    widget.configure(wrap="word")

    def on_key_release(event):
        check_and_apply_rtl(widget)

        text = widget.get("1.0", "end-1c")
        if any("\u0600" <= c <= "\u06ff" for c in text):
            widget.mark_set("insert", "end-1c")

    widget.bind("<KeyRelease>", on_key_release, add="+")
    widget.bind("<Button-3>", show_menu, add="+")

    def handle_ctrl_key(event):
        # event.state & 0x0004 checks if Ctrl is pressed
        if event.state & 0x0004:
            code = event.keycode
            if code == 65:  # A
                textbox_select_all(textbox)
                return "break"
            elif code == 90:  # Z
                textbox_undo(textbox)
                return "break"
            elif code == 89:  # Y
                textbox_redo(textbox)
                return "break"
            elif code == 67:  # C
                textbox_copy(textbox)
                return "break"
            elif code == 88:  # X
                textbox_cut(textbox)
                return "break"
            elif code == 86:  # V
                textbox_paste(textbox)
                return "break"
        return None

    # Bind to KeyPress to catch events regardless of keyboard layout
    widget.bind("<KeyPress>", handle_ctrl_key, add="+")


class PersianSubtitleToolkit(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Hide window rendering visually using alpha transparency to prevent flickering
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

        # Load assets safely (assuming 'assets' folder is alongside the script)
        # Using a resource path helper if needed, but for simplicity we rely on relative path here.
        temp_dir = os.path.dirname(__file__)
        try:
            self.iconpath = ImageTk.PhotoImage(file=self.resource_path(os.path.join(temp_dir, "assets", "icon.png")))
            heart_path = self.resource_path(os.path.join(temp_dir, "assets", "heart.png"))
            img = Image.open(heart_path)
            width_img, height_img = img.size
            # For CTk widgets (scaled, recommended)
            self.heart_image = ctk.CTkImage(
                light_image=Image.open(heart_path), dark_image=Image.open(heart_path), size=(width_img, height_img)
            )

            # For window icon (must be PhotoImage)
            self.heart_icon = ImageTk.PhotoImage(file=heart_path)
            self.wm_iconbitmap()
            self.iconphoto(False, self.iconpath)
        except Exception:
            # Fallback if assets are missing
            self.iconpath = None
            self.heart_image = None
            print("Warning: Could not load application icons.")

        # Window Configuration
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_idletasks()

        # Make the window resizable and set minimum size for stability
        self.resizable(True, True)
        self.minsize(800, 600)

        # Grid Configuration for main window
        self.grid_rowconfigure(0, weight=0)  # Top row (fixed height)
        self.grid_rowconfigure(1, weight=1)  # Middle empty frame (expandable)
        self.grid_rowconfigure(2, weight=0)  # Bottom row (fixed height)

        self.grid_columnconfigure(0, weight=1)
        self.create_widget()

        # Load config to overwrite default variable values
        self.config_manager = ConfigManager(CONFIG_FILE, DEFAULT_CONFIG)
        # Load configuration, adjust dimensions, and state logic
        self.load_config()

        self.after(100, lambda: self.start_btn.focus_set())

        # Safely reveal the window after states are established
        self.after(200, lambda: self.attributes("-alpha", 1.0))

        # Bind the configure event to the main window to detect size changes for fonts
        self.bind("<Configure>", self.adjust_button_fonts, add="+")

    def adjust_button_fonts(self, event):
        """Dynamically scale button fonts based on window width."""
        # Only process if the event is from the main window itself to avoid lag
        if event.widget == self:
            base_width = 800
            current_width = event.width

            # Calculate scale factor (min: 1.0 to keep base size, max: 1.3 to prevent overflow)
            scale = max(1.0, min(1.3, current_width / base_width))

            # Update all custom dynamic CTkFont objects
            self.btn_font_14.configure(size=int(14 * scale))
            self.btn_font_15.configure(size=int(15 * scale))
            self.btn_font_16.configure(size=int(16 * scale))
            self.btn_font_18.configure(size=int(18 * scale))

    def on_tab_changed(self):
        if self.tabview.get() == "Process":
            self.after(10, lambda: self.start_btn.focus_set())

    def create_widget(self):
        font_bold = ctk.CTkFont(size=14, weight="bold")

        # Base fonts for dynamic resizing mechanism for buttons
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

        # Path Entry (Inside Top Container)
        self.path_entry = ctk.CTkEntry(
            self.top_container,
            height=35,
            placeholder_text="Select Source Folder Which Contains Subtitles",
            font=font_bold,
        )
        self.path_entry.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")
        self.path_entry.configure(state="readonly")

        # Browse Button (Inside Top Container)
        self.browse_btn = ctk.CTkButton(self.top_container, text="Browse", height=35, font=self.btn_font_14)
        self.browse_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.browse_btn.configure(command=self.browse_folder)

        # Theme & Log Switch Frame (Inside Top Container)
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

        # Configure middle container grid layout to expand tabview fully
        self.middle_container.grid_rowconfigure(0, weight=1)
        self.middle_container.grid_columnconfigure(0, weight=1)

        # Main Tabview Structure
        self.tabview = ctk.CTkTabview(self.middle_container)
        self.tabview.grid(row=0, column=0, padx=5, pady=0, sticky="nsew")
        self.tabview.configure(command=self.on_tab_changed)

        # Add designated tabs first
        self.tab_preprocess = self.tabview.add("Pre-Process")
        self.tab_process = self.tabview.add("Process")
        self.tab_postprocess = self.tabview.add("Post-Process")
        self.tab_extra = self.tabview.add("Extra Options")

        # Safely configure font and internal text padding on the inner segmented button
        self.tabview._segmented_button.configure(font=ctk.CTkFont(size=15, weight="bold"))
        self.tabview._segmented_button.grid(
            padx=0,
            pady=0,
            ipadx=5,
            ipady=5,
            sticky="nsew",  # Sticks to all 4 sides
        )

        # Configure tab inner layout managers for future tool additions
        for tab in [self.tab_preprocess, self.tab_process, self.tab_postprocess, self.tab_extra]:
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        # --- Pre-Process Tab ---
        self.preprocess_inner_frame = ctk.CTkScrollableFrame(self.tab_preprocess, orientation="horizontal")
        self.preprocess_inner_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.preprocess_inner_frame.grid_columnconfigure(0, weight=1)

        self.chk_trim_spaces = ctk.CTkCheckBox(
            self.preprocess_inner_frame,
            text="Trim spaces from beginning and end of lines (Pre-Process)",
            font=font_bold,
        )
        self.chk_trim_spaces.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        # Checkbox for English question mark to Persian conversion
        self.chk_persian_question_mark = ctk.CTkCheckBox(
            self.preprocess_inner_frame,
            text="Convert English Question Marks to Persian (e.g., ? to ؟) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_persian_question_mark.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        # Checkbox for Arabic characters to Persian conversion
        self.chk_arabic_char = ctk.CTkCheckBox(
            self.preprocess_inner_frame,
            text="Convert Arabic Characters to Persian (e.g., ي to ی) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_arabic_char.grid(row=2, column=0, padx=5, pady=5, sticky="w")

        # Checkbox for Arabic numerals to Persian numerals conversion
        self.chk_arabic_num = ctk.CTkCheckBox(
            self.preprocess_inner_frame,
            text="Convert Arabic Numerals to Persian Numerals (e.g., ٤ to ۴) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_arabic_num.grid(row=3, column=0, padx=5, pady=5, sticky="w")

        # Checkbox for English numerals conditionally
        self.chk_english_num = ctk.CTkCheckBox(
            self.preprocess_inner_frame,
            text="Convert English Numerals to Persian (e.g., 4 to ۴) (Excludes Tags/Timecodes/Letter-attached numbers) - (Triggers Post-Process UTF-8)",
            font=font_bold,
            command=self.on_preprocess_dependency_toggle,
        )
        self.chk_english_num.grid(row=4, column=0, padx=5, pady=5, sticky="w")

        # --- Process Tab ---
        self.process_inner_frame = ctk.CTkScrollableFrame(self.tab_process)
        self.process_inner_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.process_inner_frame.grid_columnconfigure(0, weight=1)
        self.process_inner_frame.grid_rowconfigure(1, weight=1)
        self.process_inner_frame.grid_rowconfigure(3, weight=1)
        self.process_inner_frame.grid_rowconfigure(5, weight=1)

        # Bypass List
        self.chk_bypass = ctk.CTkCheckBox(
            self.process_inner_frame,
            text="Bypass List (Skip lines matching these words)",
            font=font_bold,
            command=self.toggle_bypass,
        )
        self.chk_bypass.grid(row=0, column=0, padx=5, pady=(5, 0), sticky="w")
        self.txt_bypass = ctk.CTkTextbox(self.process_inner_frame, height=160)
        self.txt_bypass.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        setup_enhanced_textbox(self.txt_bypass)

        # Remove List
        self.chk_remove = ctk.CTkCheckBox(
            self.process_inner_frame,
            text="Remove List (Delete entire line if matching these words)",
            font=font_bold,
            command=self.toggle_remove,
        )
        self.chk_remove.grid(row=2, column=0, padx=5, pady=(15, 0), sticky="w")
        self.txt_remove = ctk.CTkTextbox(self.process_inner_frame, height=160)
        self.txt_remove.grid(row=3, column=0, padx=5, pady=5, sticky="nsew")
        setup_enhanced_textbox(self.txt_remove)

        # Replace List
        self.chk_replace = ctk.CTkCheckBox(
            self.process_inner_frame,
            text="Replace List (Remove these specific words from matching lines)",
            font=font_bold,
            command=self.toggle_replace,
        )
        self.chk_replace.grid(row=4, column=0, padx=5, pady=(15, 0), sticky="w")
        self.txt_replace = ctk.CTkTextbox(self.process_inner_frame, height=160)
        self.txt_replace.grid(row=5, column=0, padx=5, pady=5, sticky="nsew")
        setup_enhanced_textbox(self.txt_replace)

        # --- Post-Process Tab ---
        self.postprocess_inner_frame = ctk.CTkScrollableFrame(self.tab_postprocess)
        self.postprocess_inner_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.postprocess_inner_frame.grid_columnconfigure(0, weight=1)

        self.chk_post_trim_spaces = ctk.CTkCheckBox(
            self.postprocess_inner_frame,
            text="Trim spaces from beginning and end of lines (Post-Process)",
            font=font_bold,
        )
        self.chk_post_trim_spaces.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        # Checkbox for Removing Empty HTML Tags
        self.chk_remove_empty_tags = ctk.CTkCheckBox(
            self.postprocess_inner_frame,
            text="Remove Empty HTML Tags (e.g., <font></font>, <b></b>)",
            font=font_bold,
        )
        self.chk_remove_empty_tags.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        # Intro Credit Subtitle Container Frame
        self.intro_credit_frame = ctk.CTkFrame(self.postprocess_inner_frame, fg_color="transparent")
        self.intro_credit_frame.grid(row=2, column=0, padx=5, pady=5, sticky="w")

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
        self.lbl_intro_credit_duration.grid(row=0, column=1, padx=(0, 5), pady=2, sticky="w")

        self.opt_intro_credit_duration = ctk.CTkOptionMenu(
            self.intro_credit_frame,
            values=["2", "3", "4", "5", "6", "7", "8", "9", "10"],
            width=65,
            command=lambda _: self.save_config(),
        )
        self.opt_intro_credit_duration.grid(row=0, column=2, padx=0, pady=2, sticky="w")
        self.opt_intro_credit_duration.set("8")

        self.txt_intro_credit_text = ctk.CTkTextbox(self.postprocess_inner_frame, height=55)
        self.txt_intro_credit_text.grid(row=3, column=0, padx=5, pady=(0, 5), sticky="ew")
        setup_enhanced_textbox(self.txt_intro_credit_text)

        # Checkbox for Removing Negative Timecodes
        self.chk_remove_negative_timecodes = ctk.CTkCheckBox(
            self.postprocess_inner_frame,
            text="Remove Negative Timecodes - (Triggers Reformat & Renumber)",
            font=font_bold,
            command=self.on_reformat_dependency_toggle,
        )
        self.chk_remove_negative_timecodes.grid(row=4, column=0, padx=5, pady=5, sticky="w")

        # Checkbox for Removing Empty Subtitles
        self.chk_remove_empty_subtitles = ctk.CTkCheckBox(
            self.postprocess_inner_frame,
            text="Remove Empty Subtitles - (Triggers Reformat & Renumber)",
            font=font_bold,
            command=self.on_reformat_dependency_toggle,
        )
        self.chk_remove_empty_subtitles.grid(row=5, column=0, padx=5, pady=5, sticky="w")

        # Checkbox for Reformat & Renumber
        self.chk_reformat_renumber = ctk.CTkCheckBox(
            self.postprocess_inner_frame,
            text="Reformat and Renumber Subtitles (Fixes numbering order and cleans block spacing)",
            font=font_bold,
            command=self.on_reformat_renumber_toggle,
        )
        self.chk_reformat_renumber.grid(row=6, column=0, padx=5, pady=5, sticky="w")

        # UTF-8 encoding save option
        self.chk_encode_utf8 = ctk.CTkCheckBox(
            self.postprocess_inner_frame,
            text="Save Final File with UTF-8 Encoding (Required for seamless Persian characters rendering)",
            font=font_bold,
            command=self.on_utf8_toggle,
        )
        self.chk_encode_utf8.grid(row=7, column=0, padx=5, pady=5, sticky="w")

        # --- Extra Options Tab ---
        self.extra_inner_frame = ctk.CTkScrollableFrame(self.tab_extra)
        self.extra_inner_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.extra_inner_frame.grid_columnconfigure(0, weight=1)

        self.chk_delete_original = ctk.CTkCheckBox(
            self.extra_inner_frame, text="Delete original subtitle file after successful process", font=font_bold
        )
        self.chk_delete_original.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.chk_detailed_logs = ctk.CTkCheckBox(
            self.extra_inner_frame,
            text="Create individual changelog file for each subtitle (Log files will be saved in '/Logs/Subtitle-Logs/' folder)",
            font=font_bold,
        )
        self.chk_detailed_logs.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        # --- Bottom Container (Row 2) ---
        self.bottom_container = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_container.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # Adjusted columns to fit the new button properly via Grid
        self.bottom_container.grid_columnconfigure(0, weight=3)
        self.bottom_container.grid_columnconfigure(1, weight=3)
        self.bottom_container.grid_columnconfigure(2, weight=2)
        self.bottom_container.grid_columnconfigure(3, weight=2)
        self.bottom_container.grid_columnconfigure(4, weight=2)
        self.bottom_container.grid_columnconfigure(5, weight=2)

        # Folder Process Button
        self.start_btn = ctk.CTkButton(
            self.bottom_container,
            text="Folder Process",
            height=45,
            font=self.btn_font_15,
            command=self.start_process_threaded,
        )
        self.start_btn.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")

        # Single File Process Button
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

        # Donate Button
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

        # Import Settings Button
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

        # Export Settings Button
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

        # Reset Button
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

    # --- Feature Dependency Methods ---
    def on_preprocess_dependency_toggle(self):
        """Enforce UTF-8 selection if any character conversion options are enabled."""
        if (
            self.chk_persian_question_mark.get() == 1
            or self.chk_arabic_char.get() == 1
            or self.chk_arabic_num.get() == 1
            or self.chk_english_num.get() == 1
        ):
            self.chk_encode_utf8.select()
        self.save_config()

    def on_utf8_toggle(self):
        """Disable character conversion features if UTF-8 is disabled since they require it."""
        if self.chk_encode_utf8.get() == 0:
            self.chk_persian_question_mark.deselect()
            self.chk_arabic_char.deselect()
            self.chk_arabic_num.deselect()
            self.chk_english_num.deselect()
        self.save_config()

    def on_reformat_dependency_toggle(self):
        """Enforce Reformat & Renumber selection if any linked post-process options are enabled."""
        if (
            self.chk_add_intro_credit.get() == 1
            or self.chk_remove_negative_timecodes.get() == 1
            or self.chk_remove_empty_subtitles.get() == 1
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
        self.toggle_intro_credit_state()
        self.save_config()

    def toggle_intro_credit_state(self):
        """Enable or disable intro credit duration and text widgets based on checkbox state."""
        if self.chk_add_intro_credit.get() == 1:
            self.opt_intro_credit_duration.configure(state="normal")
            self.txt_intro_credit_text.configure(state="normal")
        else:
            self.opt_intro_credit_duration.configure(state="disabled")
            self.txt_intro_credit_text.configure(state="disabled")

    # --- Widget Toggles ---
    def toggle_bypass(self):
        if self.chk_bypass.get() == 1:
            self.txt_bypass.configure(state="normal")
        else:
            self.txt_bypass.configure(state="disabled")
        self.save_config()

    def toggle_remove(self):
        if self.chk_remove.get() == 1:
            self.txt_remove.configure(state="normal")
        else:
            self.txt_remove.configure(state="disabled")
        self.save_config()

    def toggle_replace(self):
        if self.chk_replace.get() == 1:
            self.txt_replace.configure(state="normal")
        else:
            self.txt_replace.configure(state="disabled")
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
        # Save settings on exit
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

        # Applying maximized state after rendering with a small delay for Tkinter stability
        if config.get("is_maximized", 0) == 1:
            self.after(50, lambda: self.state("zoomed"))
        else:
            self.after(50, lambda: self.state("normal"))

        # 1. Update Path Entry first (this enables/disables the log switch state)
        folder_path = config.get("folder_path", "")
        self._update_path_entry(folder_path)

        # 2. Update Theme
        theme_mode = config.get("theme_mode", 1)
        if theme_mode == 1:
            self.theme_switch.select()
            ctk.set_appearance_mode("dark")
        else:
            self.theme_switch.deselect()
            ctk.set_appearance_mode("light")

        # 3. Update Save Logs Toggle
        # Important: Check if the switch is not disabled by _update_path_entry
        save_logs = config.get("save_logs", 0)
        if self.log_switch.cget("state") == "normal":
            if save_logs == 1:
                self.log_switch.select()
            else:
                self.log_switch.deselect()
        else:
            # If path is invalid, force deselect regardless of config
            self.log_switch.deselect()

        # 4. Load Tab Configuration Checkboxes States
        if config.get("trim_spaces", 1) == 1:
            self.chk_trim_spaces.select()
        else:
            self.chk_trim_spaces.deselect()

        if config.get("persian_question_mark", 1) == 1:
            self.chk_persian_question_mark.select()
        else:
            self.chk_persian_question_mark.deselect()

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

        # Process Tab Loading
        if config.get("bypass_enabled", 1) == 1:
            self.chk_bypass.select()
            self.txt_bypass.configure(state="normal")
        else:
            self.chk_bypass.deselect()
            self.txt_bypass.configure(state="disabled")

        self.txt_bypass.configure(state="normal")
        self.txt_bypass.delete("1.0", "end")
        self.txt_bypass.insert("1.0", config.get("bypass_list", ""))
        self.txt_bypass._original_text = config.get("bypass_list", "")
        textbox_focus_out(self.txt_bypass)
        if config.get("bypass_enabled", 1) == 0:
            self.txt_bypass.configure(state="disabled")

        if config.get("remove_enabled", 1) == 1:
            self.chk_remove.select()
            self.txt_remove.configure(state="normal")
        else:
            self.chk_remove.deselect()
            self.txt_remove.configure(state="disabled")

        self.txt_remove.configure(state="normal")
        self.txt_remove.delete("1.0", "end")
        self.txt_remove.insert("1.0", config.get("remove_list", ""))
        self.txt_remove._original_text = config.get("remove_list", "")
        textbox_focus_out(self.txt_remove)
        if config.get("remove_enabled", 1) == 0:
            self.txt_remove.configure(state="disabled")

        if config.get("replace_enabled", 1) == 1:
            self.chk_replace.select()
            self.txt_replace.configure(state="normal")
        else:
            self.chk_replace.deselect()
            self.txt_replace.configure(state="disabled")

        self.txt_replace.configure(state="normal")
        self.txt_replace.delete("1.0", "end")
        self.txt_replace.insert("1.0", config.get("replace_list", ""))
        self.txt_replace._original_text = config.get("replace_list", "")
        textbox_focus_out(self.txt_replace)
        if config.get("replace_enabled", 1) == 0:
            self.txt_replace.configure(state="disabled")

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

        self.txt_intro_credit_text.configure(state="normal")
        self.txt_intro_credit_text.delete("1.0", "end")
        credit_txt = config.get("intro_credit_text", "")
        self.txt_intro_credit_text.insert("1.0", credit_txt)
        self.txt_intro_credit_text._original_text = credit_txt
        textbox_focus_out(self.txt_intro_credit_text)

        if config.get("remove_negative_timecodes", 1) == 1:
            self.chk_remove_negative_timecodes.select()
        else:
            self.chk_remove_negative_timecodes.deselect()

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

        self.toggle_intro_credit_state()

        # 5. Final Logs
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

        # Protect default dimensions if window is maximized or incorrectly sized
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
            "trim_spaces": self.chk_trim_spaces.get(),
            "persian_question_mark": self.chk_persian_question_mark.get(),
            "arabic_char_to_persian": self.chk_arabic_char.get(),
            "arabic_num_to_persian": self.chk_arabic_num.get(),
            "english_num_to_persian": self.chk_english_num.get(),
            "bypass_enabled": self.chk_bypass.get(),
            "bypass_list": getattr(self.txt_bypass, "_original_text", ""),
            "remove_enabled": self.chk_remove.get(),
            "remove_list": getattr(self.txt_remove, "_original_text", ""),
            "replace_enabled": self.chk_replace.get(),
            "replace_list": getattr(self.txt_replace, "_original_text", ""),
            "post_trim_spaces": self.chk_post_trim_spaces.get(),
            "remove_empty_tags": self.chk_remove_empty_tags.get(),
            "add_intro_credit": self.chk_add_intro_credit.get(),
            "intro_credit_duration": self.opt_intro_credit_duration.get(),
            "intro_credit_text": getattr(self.txt_intro_credit_text, "_original_text", ""),
            "remove_negative_timecodes": self.chk_remove_negative_timecodes.get(),
            "remove_empty_subtitles": self.chk_remove_empty_subtitles.get(),
            "reformat_renumber": self.chk_reformat_renumber.get(),
            "encode_utf8": self.chk_encode_utf8.get(),
            "delete_original": self.chk_delete_original.get(),
            "detailed_subtitle_logs": self.chk_detailed_logs.get(),
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

        self.chk_trim_spaces.select()
        self.chk_persian_question_mark.select()
        self.chk_arabic_char.select()
        self.chk_arabic_num.select()
        self.chk_english_num.select()

        self.chk_bypass.select()
        self.txt_bypass.configure(state="normal")
        self.txt_bypass.delete("1.0", "end")
        self.txt_bypass._original_text = ""
        check_and_apply_rtl(self.txt_bypass._textbox)

        self.chk_remove.select()
        self.txt_remove.configure(state="normal")
        self.txt_remove.delete("1.0", "end")
        self.txt_remove._original_text = ""
        check_and_apply_rtl(self.txt_remove._textbox)

        self.chk_replace.select()
        self.txt_replace.configure(state="normal")
        self.txt_replace.delete("1.0", "end")
        self.txt_replace._original_text = ""
        check_and_apply_rtl(self.txt_replace._textbox)

        self.chk_post_trim_spaces.select()
        self.chk_remove_empty_tags.select()
        self.chk_add_intro_credit.deselect()
        self.opt_intro_credit_duration.set("8")
        self.txt_intro_credit_text.configure(state="normal")
        self.txt_intro_credit_text.delete("1.0", "end")
        self.txt_intro_credit_text._original_text = ""
        check_and_apply_rtl(self.txt_intro_credit_text._textbox)

        self.chk_remove_negative_timecodes.select()
        self.chk_remove_empty_subtitles.select()
        self.chk_reformat_renumber.select()
        self.chk_encode_utf8.select()
        self.chk_delete_original.deselect()
        self.chk_detailed_logs.select()

        self.toggle_intro_credit_state()

    def import_settings(self):
        file_path = filedialog.askopenfilename(title="Select Configuration File", filetypes=[("JSON files", "*.json")])

        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                imported_config = json.load(f)

            # Validate app name
            if imported_config.get("app_name") != APP_NAME:
                messagebox.showerror("Error", "Invalid configuration file for this application.")
                return

            # Update only valid existing keys (excluding identity keys)
            excluded_keys = ["app_name", "app_version"]
            current_config = self.config_manager.load()

            updated_count = 0
            for key, value in imported_config.items():
                if key in current_config and key not in excluded_keys:
                    current_config[key] = value
                    updated_count += 1

            if updated_count > 0:
                # Save the new config and reload UI
                self.config_manager.save(current_config)
                self.load_config()
                self.write_log(f"Settings imported successfully from: {file_path}")
                messagebox.showinfo("Success", "Settings have been imported and applied successfully.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to import settings: {str(e)}")

    def export_settings(self):
        # Generate unique filename
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
            # Save current state first
            self.save_config()
            # Get latest config from file
            config_data = self.config_manager.load()

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)

            self.write_log(f"Settings exported successfully to: {file_path}")
            messagebox.showinfo("Success", f"Settings exported to:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export settings: {str(e)}")

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
            self.write_log(f"Target folder successfully changed.")

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
        self.save_config()

    def _run_processing_pipeline(self, processor, is_single_file=False):
        # Executes the common processing and reporting logic
        processor.run()
        successful = getattr(processor, "successful_count", 0)
        failed = getattr(processor, "failed_count", 0)
        total = successful + failed
        elapsed = getattr(processor, "elapsed_time", 0)
        lines_proc = getattr(processor, "total_lines_processed", 0)
        lines_per_sec = lines_proc / elapsed if elapsed > 0 else 0

        if not is_single_file:
            summary_message = (
                f"Subtitle processing has completed.\n\n"
                f"Processed {lines_proc} lines in {elapsed:.2f} seconds ({lines_per_sec:.2f} lines/sec).\n\n"
                f"Total files discovered: {total}\n"
                f"Successfully processed: {successful}\n"
                f"Failed / Skipped: {failed}\n\n"
                f"Output files are located in the 'Outputs' folder within the selected directory."
            )
        else:
            summary_message = (
                f"Single file processing has completed.\n\n"
                f"Processed {lines_proc} lines in {elapsed:.2f} seconds ({lines_per_sec:.2f} lines/sec).\n\n"
                f"Total files selected: {total}\n"
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

            self.attributes("-disabled", False)
            self.lift()
            self.focus_force()

        self.after(0, finish)

    def _get_run_options(self):
        # Helper to collect options dictionary
        return {
            "trim_spaces": self.chk_trim_spaces.get(),
            "persian_question_mark": self.chk_persian_question_mark.get(),
            "arabic_char_to_persian": self.chk_arabic_char.get(),
            "arabic_num_to_persian": self.chk_arabic_num.get(),
            "english_num_to_persian": self.chk_english_num.get(),
            "bypass_enabled": self.chk_bypass.get(),
            "bypass_list": getattr(self.txt_bypass, "_original_text", ""),
            "remove_enabled": self.chk_remove.get(),
            "remove_list": getattr(self.txt_remove, "_original_text", ""),
            "replace_enabled": self.chk_replace.get(),
            "replace_list": getattr(self.txt_replace, "_original_text", ""),
            "post_trim_spaces": self.chk_post_trim_spaces.get(),
            "remove_empty_tags": self.chk_remove_empty_tags.get(),
            "add_intro_credit": self.chk_add_intro_credit.get(),
            "intro_credit_duration": self.opt_intro_credit_duration.get(),
            "intro_credit_text": getattr(self.txt_intro_credit_text, "_original_text", ""),
            "remove_negative_timecodes": self.chk_remove_negative_timecodes.get(),
            "remove_empty_subtitles": self.chk_remove_empty_subtitles.get(),
            "reformat_renumber": self.chk_reformat_renumber.get(),
            "encode_utf8": self.chk_encode_utf8.get(),
            "delete_original": self.chk_delete_original.get(),
            "detailed_subtitle_logs": self.chk_detailed_logs.get(),
        }

    def start_process_threaded(self):
        threading.Thread(target=self.start_process, daemon=True).start()

    def start_process(self):
        current_path = self.path_entry.get()
        if not current_path:
            messagebox.showwarning("Error", "Please select a folder first.")
            return

        self.attributes("-disabled", True)

        # Save settings on triggering task execution
        self.save_config()

        run_options = self._get_run_options()

        processor = SubtitleProcessor(current_path, options=run_options)
        self._run_processing_pipeline(processor, is_single_file=False)

    # Adding thread logic for processing single files smoothly without freezing the UI
    def start_single_process_threaded(self):
        threading.Thread(target=self.start_single_process, daemon=True).start()

    # The actual method handling single file selection and processing
    def start_single_process(self):
        selected_files = filedialog.askopenfilenames(title="Select SRT Files", filetypes=[("Subtitle Files", "*.srt")])

        if not selected_files:
            return

        count = len(selected_files)
        confirm = messagebox.askyesno(
            "Confirm Process", f"Do you want to process {count} selected file(s) with the current settings?"
        )

        if not confirm:
            return

        self.attributes("-disabled", True)
        self.save_config()

        run_options = self._get_run_options()

        # Empty string for folder path, passing target_files explicitly
        processor = SubtitleProcessor("", options=run_options, target_files=selected_files)
        self._run_processing_pipeline(processor, is_single_file=True)

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

        # Set icon safely for CTk
        if self.heart_icon:
            top.after(250, lambda: top.iconphoto(False, self.heart_icon))

        # Center the window
        width = 500
        height = 300
        x = (top.winfo_screenwidth() // 2) - (width // 2)
        y = (top.winfo_screenheight() // 2) - (height // 2)
        top.geometry(f"{width}x{height}+{x}+{y}")

        # Configure grid for Toplevel
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=0)

        # ==== Layout starts ====

        # Donate image (clickable)
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

        # USDT Label
        usdt_label = ctk.CTkLabel(top, text="USDT (Tether) – TRC20 Wallet Address :", font=("Segoe UI", 14, "bold"))
        usdt_label.grid(row=1, column=0, columnspan=2, pady=(30, 5), sticky="w", padx=20)

        # Entry field (readonly)
        wallet_address = "TGoKk5zD3BMSGbmzHnD19m9YLpH5ZP8nQe"
        wallet_entry = ctk.CTkEntry(top, width=300)
        wallet_entry.insert(0, wallet_address)
        wallet_entry.configure(state="readonly")
        wallet_entry.grid(row=2, column=0, padx=(20, 10), pady=5, sticky="ew")

        # Copy button
        copy_btn = ctk.CTkButton(top, text="Copy", width=80)
        copy_btn.grid(row=2, column=1, padx=(0, 20), pady=5, sticky="w")

        tooltip = None

        def copy_wallet():
            nonlocal tooltip
            self.clipboard_clear()
            self.clipboard_append(wallet_address)
            self.update()

            # Remove old tooltip if exists
            if tooltip:
                tooltip.hidetip()
                tooltip = None

            tooltip = Hovertip(copy_btn, "Copied to clipboard!")
            tooltip.showtip()

            # Hide after 2 seconds
            def hide_tip():
                if tooltip:
                    tooltip.hidetip()

            top.after(2000, hide_tip)

        copy_btn.configure(command=copy_wallet)

        top.after(200, top.deiconify)


if __name__ == "__main__":
    app = PersianSubtitleToolkit()
    app.mainloop()
