import os
import sys

APP_VERSION = "0.4.3"
APP_NAME = "Persian Subtitle Toolkit"
CONFIG_FILENAME = "config.json"

# Default configuration structure
DEFAULT_CONFIG = {
    "app_name": APP_NAME,
    "app_version": APP_VERSION,
    "folder_path": "",
    "theme_mode": 1,
    "save_logs": 0,
    "trim_spaces": 1,
    "bypass_enabled": 1,
    "bypass_list": "",
    "remove_enabled": 1,
    "remove_list": "",
    "replace_enabled": 1,
    "replace_list": "",
    "post_trim_spaces": 1,
    "delete_original": 0,
    "detailed_subtitle_logs": 1,
}

# Determine configuration directory based on OS
if sys.platform == "win32":
    CONFIG_DIR = os.path.join(os.getenv("LOCALAPPDATA", "/tmp"), APP_NAME)
else:
    CONFIG_DIR = os.path.join(os.getenv("HOME", "/tmp"), f".{APP_NAME}")

CONFIG_FILE = os.path.join(CONFIG_DIR, CONFIG_FILENAME)
os.makedirs(CONFIG_DIR, exist_ok=True)
