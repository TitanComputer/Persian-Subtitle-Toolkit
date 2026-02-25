from core import *
import customtkinter as ctk
from customtkinter import filedialog
import tkinter as tk
from tkinter import messagebox
from PIL import ImageTk, Image
from idlelib.tooltip import Hovertip
import webbrowser


class PersianSubtitleToolkit(ctk.CTk):
    def __init__(self):
        super().__init__()
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
        width = 1000
        height = 800
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(False, False)

        # Grid Configuration for main window
        self.grid_rowconfigure(0, weight=0)  # Top row (fixed height)
        self.grid_rowconfigure(1, weight=1)  # Middle empty frame (expandable)
        self.grid_rowconfigure(2, weight=0)  # Bottom row (fixed height)

        self.grid_columnconfigure(0, weight=1)
        self.create_widget()

        # Load config to overwrite default variable values
        self.config_manager = ConfigManager(CONFIG_FILE, DEFAULT_CONFIG)
        self.load_config()

    def create_widget(self):
        font_bold = ctk.CTkFont(size=14, weight="bold")

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
        self.browse_btn = ctk.CTkButton(self.top_container, text="Browse", height=35, font=font_bold)
        self.browse_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.browse_btn.configure(command=self.browse_folder)

        # Theme & Log Switch Frame (Inside Top Container)
        self.theme_frame = ctk.CTkFrame(self.top_container, fg_color="transparent")
        self.theme_frame.grid(row=0, column=2, padx=(5, 0), pady=0, sticky="nsew")
        self.theme_frame.grid_columnconfigure(0, weight=1)
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

        # --- Middle Container (Row 1) ---
        # This frame is currently empty and will hold the main logic UI later
        self.middle_container = ctk.CTkFrame(self)
        self.middle_container.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # --- Bottom Container (Row 2) ---
        self.bottom_container = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_container.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")

        self.bottom_container.grid_columnconfigure(0, weight=5)
        self.bottom_container.grid_columnconfigure(1, weight=3)
        self.bottom_container.grid_columnconfigure(2, weight=2)

        # Start Button
        self.start_btn = ctk.CTkButton(
            self.bottom_container,
            text="Start Process",
            height=45,
            font=ctk.CTkFont(size=18, weight="bold"),
            command=self.start_process_threaded,
        )
        self.start_btn.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")

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
            font=ctk.CTkFont(size=18, weight="bold"),
            command=self.donate,
        )
        self.donate_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Import Settings Button
        self.import_btn = ctk.CTkButton(
            self.bottom_container,
            text="Import Settings",
            height=45,
            fg_color="#b434db",
            hover_color="#9b2bb8",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self.import_settings,
        )
        self.import_btn.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        # Export Settings Button
        self.export_btn = ctk.CTkButton(
            self.bottom_container,
            text="Export Settings",
            height=45,
            fg_color="#27ae60",
            hover_color="#186d3b",
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self.export_settings,
        )
        self.export_btn.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        # Reset Button
        self.reset_button = ctk.CTkButton(
            self.bottom_container,
            text="Reset Settings",
            height=45,
            fg_color="#A9A9A9",
            hover_color="#808080",
            text_color="#000000",
            font=ctk.CTkFont(size=18, weight="bold"),
            command=self._reset_settings,
        )
        self.reset_button.grid(row=0, column=4, padx=(5, 0), pady=5, sticky="ew")

    def resource_path(self, relative_path):
        temp_dir = os.path.dirname(__file__)
        return os.path.join(temp_dir, relative_path)

    def on_close(self):
        """
        Handles application shutdown, cleans up the lock file, saves config,
        and checks if a process is running before exiting.
        """
        # Save settings on exit
        self.save_config()
        self.lock.release()
        self.destroy()

    # --- Config Management Methods ---
    def load_config(self):
        config = self.config_manager.load()

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

        # 4. Final Logs
        sys_info = Logger.get_system_info()
        self.write_log(f"System Info: {sys_info}")
        self.write_log("Application config loaded/reloaded.")

    def save_config(self):
        current_path = self.path_entry.get()
        theme_val = self.theme_switch.get()
        log_val = self.log_switch.get()
        self.write_log("Config saved.")
        self.config_manager.save(current_path, theme_val, log_val)

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
        self.log_switch.deselect()
        self.log_switch.configure(state="disabled")

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
                self.config_manager.save(
                    current_config.get("folder_path", ""),
                    current_config.get("theme_mode", 1),
                    current_config.get("save_logs", 0),
                )
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

    def on_close(self):
        self.write_log("Application closing.")
        self.save_config()
        self.lock.release()
        self.destroy()

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
            messagebox.showinfo("Logs Enabled", "Logs will be saved in the selected folder under /logs directory.")
            Logger.log("Logging enabled by user.", self.path_entry.get(), True)
        else:
            Logger.log("Logging disabled by user.", self.path_entry.get(), True)
        self.save_config()

    def change_theme(self):
        mode = "dark" if self.theme_switch.get() == 1 else "light"
        ctk.set_appearance_mode(mode)
        self.write_log(f"Appearance mode changed to {mode}")
        self.save_config()

    def start_process_threaded(self):
        threading.Thread(target=self.start_process, daemon=True).start()

    def start_process(self):
        current_path = self.path_entry.get()
        if not current_path:
            messagebox.showwarning("Error", "Please select a folder first.")
            return

        processor = SubtitleProcessor(current_path)
        processor.run()

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
