import os
import sys

APP_VERSION = "0.10.1"
APP_NAME = "Persian Subtitle Toolkit"
CONFIG_FILENAME = "config.json"

# Default configuration structure
DEFAULT_CONFIG = {
    "app_name": APP_NAME,
    "app_version": APP_VERSION,
    "folder_path": "",
    "theme_mode": 1,
    "window_width": 800,
    "window_height": 600,
    "is_maximized": 0,
    "save_logs": 0,
    "trim_spaces": 1,
    "persian_question_mark": 1,
    "arabic_char_to_persian": 1,
    "arabic_num_to_persian": 1,
    "english_num_to_persian": 1,
    "bypass_enabled": 1,
    "bypass_list": "",
    "remove_enabled": 1,
    "remove_list": "",
    "replace_enabled": 1,
    "replace_list": "",
    "post_trim_spaces": 1,
    "remove_empty_tags": 1,
    "add_intro_credit": 0,
    "intro_credit_duration": "8",
    "intro_credit_text": "",
    "remove_negative_timecodes": 1,
    "remove_empty_subtitles": 1,
    "reformat_renumber": 1,
    "encode_utf8": 1,
    "delete_original": 0,
    "detailed_subtitle_logs": 1,
    "enable_dnd": 1,
}

# Determine configuration directory based on OS
if sys.platform == "win32":
    CONFIG_DIR = os.path.join(os.getenv("LOCALAPPDATA", "/tmp"), APP_NAME)
else:
    CONFIG_DIR = os.path.join(os.getenv("HOME", "/tmp"), f".{APP_NAME}")

CONFIG_FILE = os.path.join(CONFIG_DIR, CONFIG_FILENAME)
os.makedirs(CONFIG_DIR, exist_ok=True)
