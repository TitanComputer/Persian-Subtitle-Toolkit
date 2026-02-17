import customtkinter as ctk
from customtkinter import filedialog
import tkinter as tk
from tkinter import messagebox
from PIL import ImageTk, Image
from idlelib.tooltip import Hovertip
import os
import threading
import re
import string
import sys
import time
import webbrowser
import json

APP_VERSION = "1.0.0"
APP_NAME = "Persian Subtitle Toolkit"
CONFIG_FILENAME = "config.json"

# Default configuration structure
DEFAULT_CONFIG = {
    "app_name": APP_NAME,
    "app_version": APP_VERSION,
    "folder_path": "",
}

# Determine configuration directory based on OS
if sys.platform == "win32":
    CONFIG_DIR = os.path.join(os.getenv("LOCALAPPDATA", "/tmp"), APP_NAME)
else:
    CONFIG_DIR = os.path.join(os.getenv("HOME", "/tmp"), f".{APP_NAME}")

CONFIG_FILE = os.path.join(CONFIG_DIR, CONFIG_FILENAME)
os.makedirs(CONFIG_DIR, exist_ok=True)

# --- Single Instance Logic START with Timeout ---
APP_LOCK_DIR = os.path.join(os.getenv("LOCALAPPDATA", os.getenv("HOME", "/tmp")), APP_NAME)
LOCK_FILE = os.path.join(APP_LOCK_DIR, "app.lock")
LOCK_TIMEOUT_SECONDS = 60

os.makedirs(APP_LOCK_DIR, exist_ok=True)
IS_LOCK_CREATED = False

if os.path.exists(LOCK_FILE):
    try:
        lock_age = time.time() - os.path.getmtime(LOCK_FILE)

        if lock_age > LOCK_TIMEOUT_SECONDS:
            os.remove(LOCK_FILE)
            print(f"Removed stale lock file (Age: {int(lock_age)}s).")
        else:
            try:
                temp_root = tk.Tk()
                temp_root.withdraw()
                messagebox.showwarning(
                    f"{APP_NAME} v{APP_VERSION}",
                    f"{APP_NAME} is already running.\nOnly one instance is allowed.",
                )
                temp_root.destroy()
            except Exception:
                print("Application is already running.")

            sys.exit(0)

    except Exception as e:
        print(f"Error checking lock file: {e}. Exiting.")
        sys.exit(0)

try:
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    IS_LOCK_CREATED = True
except Exception as e:
    print(f"Could not create lock file: {e}")
    sys.exit(1)

# --- Single Instance Logic END with Timeout ---


class PersianSubtitleToolkit(ctk.CTk):
    def __init__(self):
        super().__init__()
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
        width = 800
        height = 800
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")

        # Grid Configuration for main window
        self.grid_rowconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=4, uniform="col")
        self.grid_columnconfigure(1, weight=1, uniform="col")
        font_bold = ctk.CTkFont(size=14, weight="bold")

        # Row 1: Entry + Browse Button
        self.path_entry = ctk.CTkEntry(self, height=20, placeholder_text="Select Target Folder", font=font_bold)
        self.path_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="nsew")
        self.path_entry.configure(state="readonly")

        self.browse_btn = ctk.CTkButton(self, text="Browse", height=20)
        self.browse_btn.grid(row=0, column=1, padx=(5, 10), pady=10, sticky="nsew")
        self.browse_btn.configure(font=font_bold)
        self.browse_btn.configure(command=self.browse_folder)

        # Row 3: Start + Donate Buttons (inside a local frame)
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")
        button_frame.grid_propagate(False)
        button_frame.configure(height=15)
        # Local grid configuration (no changes to main layout)
        button_frame.grid_columnconfigure(0, weight=5)
        button_frame.grid_columnconfigure(1, weight=3)
        button_frame.grid_columnconfigure(2, weight=2)
        button_frame.grid_rowconfigure(0, weight=1)

        # Start Button
        self.start_btn = ctk.CTkButton(
            button_frame,
            text="Start Process",
            font=ctk.CTkFont(size=18, weight="bold"),
            command=self.start_process_threaded,
        )
        self.start_btn.grid(row=0, column=0, padx=(0, 5), sticky="nsew")

        # Donate Button
        self.donate_button = ctk.CTkButton(
            button_frame,
            text="Donate",
            image=self.heart_image,
            compound="right",
            fg_color="#FFD700",
            hover_color="#FFC400",
            text_color="#000000",
            font=ctk.CTkFont(size=18, weight="bold"),
            command=self.donate,
        )
        self.donate_button.grid(row=0, column=1, padx=5, sticky="nsew")

        # Reset Button
        self.reset_button = ctk.CTkButton(
            button_frame,
            text="Reset Settings",
            fg_color="#A9A9A9",  # Dark Gray
            hover_color="#808080",  # Gray
            text_color="#000000",
            font=ctk.CTkFont(size=18, weight="bold"),
            command=self._reset_settings,
        )
        self.reset_button.grid(row=0, column=2, padx=(5, 0), sticky="nsew")

        # --- Lock Updater Control START ---
        self.lock_refresh_active = True
        if "IS_LOCK_CREATED" in globals() and IS_LOCK_CREATED:
            self.lock_thread = threading.Thread(target=self._lock_updater, daemon=True)
            self.lock_thread.start()
            print("Started lock refresh thread.")
        # --- Lock Updater Control END ---

        # Load config to overwrite default variable values
        self.load_config()

    def _reset_settings(self):
        """Resets all configuration settings to their default values."""
        self._apply_default_config()
        self.save_config()
        messagebox.showinfo("Settings Reset", "All settings have been reset to default values.")

    def _lock_updater(self):
        """
        Periodically updates the lock file timestamp to keep the lock fresh.
        Runs in a separate thread.
        """
        global IS_LOCK_CREATED
        if not IS_LOCK_CREATED:
            return

        while self.lock_refresh_active:
            try:
                os.utime(LOCK_FILE, None)
                print("Lock file timestamp updated.")
            except Exception as e:
                print(f"Error refreshing lock: {e}")
                break

            time.sleep(LOCK_TIMEOUT_SECONDS / 2)

        print("Lock refresh thread stopped.")

    def on_close(self):
        """
        Handles application shutdown, cleans up the lock file, saves config,
        and checks if a process is running before exiting.
        """
        # Save settings on exit
        self.save_config()

        # --- Single Instance Cleanup START ---
        global IS_LOCK_CREATED
        if "IS_LOCK_CREATED" in globals() and IS_LOCK_CREATED:
            self.lock_refresh_active = False
            try:
                if self.lock_thread.is_alive():
                    self.lock_thread.join(0.5)
                os.remove(LOCK_FILE)
            except Exception as e:
                print(f"Could not remove lock file: {e}")
        # --- Single Instance Cleanup END ---

        self.destroy()

    def resource_path(self, relative_path):
        temp_dir = os.path.dirname(__file__)
        return os.path.join(temp_dir, relative_path)

    # --- Config Management Methods ---
    def load_config(self):
        """Loads configuration from config.json or creates default config if missing."""
        if not os.path.isfile(CONFIG_FILE):
            # No config exists → create default
            self._apply_default_config()
            self.save_config()
            return

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            # Corrupted config → fallback to default
            self._apply_default_config()
            self.save_config()
            return

        # Load values safely
        folder_path = config.get("folder_path", "")

        # Apply folder path
        if folder_path and os.path.isdir(folder_path):
            self.path_entry.configure(state="normal")
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder_path)
            self.path_entry.configure(state="readonly")

    def _apply_default_config(self):
        """Applies values from DEFAULT_CONFIG to UI."""
        # Reset folder path
        self.path_entry.configure(state="normal")
        self.path_entry.delete(0, "end")
        self.path_entry.configure(placeholder_text="Select Target Folder")
        self.path_entry.configure(state="readonly")

    def save_config(self):
        """Saves current application settings to config.json."""
        folder_path = self.path_entry.get()

        config = {
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "folder_path": folder_path if os.path.isdir(folder_path) else "",
        }

        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def browse_folder(self):
        initial_dir = (
            self.path_entry.get() if os.path.isdir(self.path_entry.get()) else os.path.expanduser("~/Documents")
        )
        folder_selected = filedialog.askdirectory(initialdir=initial_dir, title="Select Target Folder")
        if folder_selected:
            self.path_entry.configure(state="normal")
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder_selected)
            self.path_entry.configure(state="readonly")

    def start_process_threaded(self):
        threading.Thread(target=self.start_process, daemon=True).start()

    def start_process(self):
        pass

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
