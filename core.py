from utils import *
import os
import re


def build_flexible_regex(word):
    """
    Creates a regex pattern that ignores spaces, dots, zero-width non-joiners (\u200c),
    kashida (ـ), and various dashes/underscores between the characters of the provided word.
    Compiles with re.IGNORECASE to support case-insensitive English matching.
    """
    # Consolidated ignored characters into a single variable to avoid duplication
    # Added _, -, \u2013 (en-dash), and \u2014 (em-dash) to catch all line stretching variations
    ignored_chars = r"[\s\.\u200cـ\u064b-\u0652\u200b-\u200f\u202a-\u202e_\-\u2013\u2014]"

    clean_word = re.sub(ignored_chars, "", word)
    if not clean_word:
        return None

    # Escape characters safely and join with optional ignored characters pattern
    char_patterns = []
    for c in clean_word:
        if c in ("ی", "ي", "ى"):
            char_patterns.append(r"[یيى]")
        elif c in ("ک", "ك"):
            char_patterns.append(r"[کك]")
        elif c in ("ا", "آ", "أ", "إ"):
            char_patterns.append(r"[اآأإ]")
        elif c in ("ه", "ة"):
            char_patterns.append(r"[هة]")
        else:
            char_patterns.append(re.escape(c))

    pattern = f"{ignored_chars}*".join(char_patterns)
    return re.compile(pattern, re.IGNORECASE)


class SubtitleProcessor:
    # Added target_files to handle single file process mode
    def __init__(self, folder_path, options=None, target_files=None):
        self.folder_path = folder_path
        self.options = options if options else {}
        self.target_files = target_files
        self.successful_count = 0
        self.failed_count = 0

    def run(self):
        # Determine files to process based on execution mode
        if self.target_files:
            srt_files_paths = self.target_files
            if srt_files_paths:
                Logger.log_process(
                    f"Single file process started. Found {len(srt_files_paths)} file(s).",
                    os.path.dirname(srt_files_paths[0]),
                )
        else:
            if not self.folder_path or not os.path.isdir(self.folder_path):
                return
            all_files = os.listdir(self.folder_path)
            srt_files = [f for f in all_files if f.lower().endswith(".srt")]
            if not srt_files:
                Logger.log_process("No subtitle files (.srt) found to process.", self.folder_path)
                return
            srt_files_paths = [os.path.join(self.folder_path, f) for f in srt_files]
            Logger.log_process(f"Process started. Found {len(srt_files_paths)} file(s).", self.folder_path)

        # Extract Process configuration variables
        bypass_enabled = self.options.get("bypass_enabled", 1)
        bypass_list = [w.strip() for w in self.options.get("bypass_list", "").split("\n") if w.strip()]

        remove_enabled = self.options.get("remove_enabled", 1)
        remove_list = [w.strip() for w in self.options.get("remove_list", "").split("\n") if w.strip()]

        replace_enabled = self.options.get("replace_enabled", 1)
        replace_list = [w.strip() for w in self.options.get("replace_list", "").split("\n") if w.strip()]

        post_trim_spaces = self.options.get("post_trim_spaces", 1)

        # Dictionaries for character and number conversion
        arabic_to_persian_chars = {"ي": "ی", "ك": "ک", "ة": "ه", "ؤ": "و", "إ": "ا", "أ": "ا"}
        arabic_numerals = {
            "٠": "۰",
            "١": "۱",
            "٢": "۲",
            "٣": "۳",
            "٤": "۴",
            "٥": "۵",
            "٦": "۶",
            "٧": "۷",
            "٨": "۸",
            "٩": "۹",
        }
        english_numerals = {
            "0": "۰",
            "1": "۱",
            "2": "۲",
            "3": "۳",
            "4": "۴",
            "5": "۵",
            "6": "۶",
            "7": "۷",
            "8": "۸",
            "9": "۹",
        }

        # Regex patterns to identify timecodes and index lines accurately
        timecode_pattern = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}")
        index_pattern = re.compile(r"^\d+\s*$")

        for file_path in srt_files_paths:
            filename = os.path.basename(file_path)
            current_file_dir = os.path.dirname(file_path)

            # Define output directory path dynamically for the current file
            output_dir = os.path.join(current_file_dir, "Outputs")
            os.makedirs(output_dir, exist_ok=True)

            Logger.log_process(f"Identified file: {filename}", current_file_dir)

            try:
                # Smart encoding reader. Tries UTF-8 first, falls back to cp1256 (Windows Arabic)
                file_encoding = "utf-8"
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                except UnicodeDecodeError:
                    file_encoding = "cp1256"
                    with open(file_path, "r", encoding="cp1256", errors="ignore") as f:
                        lines = f.readlines()

                processed_lines = []
                file_has_changes = False

                if self.options.get("detailed_subtitle_logs", 1):
                    Logger.log_subtitle_change(current_file_dir, filename, f"Started tracking changes for: {filename}")

                for index, line in enumerate(lines, start=1):
                    original_line = line
                    current_line = original_line

                    # Check if line is standard subtitle timecode or index number
                    is_timecode_or_index = bool(
                        timecode_pattern.match(current_line) or index_pattern.match(current_line)
                    )

                    # Apply Pre-Process Option: Trim Spaces
                    if self.options.get("trim_spaces", 1):
                        stripped = current_line.strip()
                        # Preserving structural carriage returns of SRT format
                        if current_line.endswith("\n"):
                            current_line = stripped + "\n"
                        elif current_line.endswith("\r\n"):
                            current_line = stripped + "\r\n"
                        else:
                            current_line = stripped

                    # Log Pre-Process Changes
                    if current_line != original_line:
                        file_has_changes = True
                        if self.options.get("detailed_subtitle_logs", 1):
                            orig_clean = original_line.rstrip("\n")
                            curr_clean = current_line.rstrip("\n")
                            log_msg = f'Line {index} modified | Option: Pre-Process Trim Spaces | Before: "{orig_clean}" -> After: "{curr_clean}"'
                            Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    # 1. Convert Arabic Characters to Persian
                    if self.options.get("arabic_char_to_persian", 1):
                        before_char = current_line
                        for k, v in arabic_to_persian_chars.items():
                            current_line = current_line.replace(k, v)
                        if current_line != before_char:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_char.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                log_msg = f'Line {index} modified | Option: Pre-Process Arabic Chars | Before: "{b_clean}" -> After: "{c_clean}"'
                                Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    # 2. Convert Arabic Numerals to Persian Numerals
                    if self.options.get("arabic_num_to_persian", 1):
                        before_anum = current_line
                        for k, v in arabic_numerals.items():
                            current_line = current_line.replace(k, v)
                        if current_line != before_anum:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_anum.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                log_msg = f'Line {index} modified | Option: Pre-Process Arabic Numerals | Before: "{b_clean}" -> After: "{c_clean}"'
                                Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    # 3. Convert English Numerals to Persian Numerals conditionally
                    if self.options.get("english_num_to_persian", 1) and not is_timecode_or_index:
                        before_enum = current_line

                        def replace_eng_num(match):
                            return "".join(english_numerals.get(char, char) for char in match.group(1))

                        # Split text by HTML tags to preserve numbers inside tags (e.g. font size, colors)
                        parts = re.split(r"(<[^>]+>)", current_line)
                        for i in range(len(parts)):
                            if not parts[i].startswith("<"):
                                # Lookbehind/Lookahead to ensure numbers are not attached to english letters
                                parts[i] = re.sub(r"(?<![a-zA-Z])(\d+)(?![a-zA-Z])", replace_eng_num, parts[i])

                        current_line = "".join(parts)
                        if current_line != before_enum:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_enum.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                log_msg = f'Line {index} modified | Option: Pre-Process English Numerals | Before: "{b_clean}" -> After: "{c_clean}"'
                                Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    # --- Process Options ---
                    is_bypassed = False
                    if bypass_enabled:
                        for word in bypass_list:
                            reg = build_flexible_regex(word)
                            if reg and reg.search(current_line):
                                is_bypassed = True
                                if self.options.get("detailed_subtitle_logs", 1):
                                    log_msg = f'Line {index} bypassed | Matched "{word}" in Bypass List. No further process changes applied.'
                                    Logger.log_subtitle_change(current_file_dir, filename, log_msg)
                                break

                    if not is_bypassed:
                        is_removed = False

                        # Process Option: Remove List
                        if remove_enabled:
                            for word in remove_list:
                                reg = build_flexible_regex(word)
                                if reg and reg.search(current_line):
                                    is_removed = True
                                    file_has_changes = True
                                    if self.options.get("detailed_subtitle_logs", 1):
                                        curr_clean = current_line.rstrip("\n")
                                        log_msg = f'Line {index} removed | Matched "{word}" in Remove List. Entire line deleted. The line was: "{curr_clean}"'
                                        Logger.log_subtitle_change(current_file_dir, filename, log_msg)
                                    current_line = None
                                    break

                        # If removed, skip remaining processing steps and do not append this line
                        if is_removed:
                            continue

                        # Process Option: Replace List
                        if replace_enabled and current_line:
                            for word in replace_list:
                                reg = build_flexible_regex(word)
                                if reg and reg.search(current_line):
                                    before_replace = current_line
                                    current_line = reg.sub("", current_line)
                                    if current_line != before_replace:
                                        file_has_changes = True
                                        if self.options.get("detailed_subtitle_logs", 1):
                                            before_clean = before_replace.rstrip("\n")
                                            curr_clean = current_line.rstrip("\n")
                                            log_msg = f'Line {index} modified | Option: Replace List (Matched "{word}") | Before: "{before_clean}" -> After: "{curr_clean}"'
                                            Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                        # --- Post-Process Options ---
                        # Apply Post-Process Option: Trim Spaces
                        if post_trim_spaces and current_line:
                            before_post = current_line
                            stripped = current_line.strip()
                            if current_line.endswith("\n"):
                                current_line = stripped + "\n"
                            elif current_line.endswith("\r\n"):
                                current_line = stripped + "\r\n"
                            else:
                                current_line = stripped

                            if current_line != before_post:
                                file_has_changes = True
                                if self.options.get("detailed_subtitle_logs", 1):
                                    before_clean = before_post.rstrip("\n")
                                    curr_clean = current_line.rstrip("\n")
                                    log_msg = f'Line {index} modified | Option: Post-Process Trim Spaces | Before: "{before_clean}" -> After: "{curr_clean}"'
                                    Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    # Finally, append the line if it wasn't removed completely
                    if current_line is not None:
                        processed_lines.append(current_line)

                # Construct output file path structure
                name_part, ext_part = os.path.splitext(filename)
                output_filename = f"{name_part}_Edited{ext_part}"
                output_file_path = os.path.join(output_dir, output_filename)

                # Use explicit UTF-8 if setting is enabled, otherwise use original detected encoding
                out_encoding = "utf-8" if self.options.get("encode_utf8", 1) else file_encoding

                with open(output_file_path, "w", encoding=out_encoding) as f:
                    f.writelines(processed_lines)

                Logger.log_process(f"Processed and saved successfully: {output_filename}", current_file_dir)
                if self.options.get("detailed_subtitle_logs", 1):
                    Logger.log_subtitle_change(
                        current_file_dir, filename, f"Finished tracking. Total changes occurred: {file_has_changes}"
                    )

                # Post processing clean up option: Delete Original
                if self.options.get("delete_original", 0):
                    os.remove(file_path)
                    Logger.log_process(f"Original file deleted by request: {filename}", current_file_dir)

                # Increment successful tracking counter
                self.successful_count += 1

            except Exception as e:
                Logger.log_process(f"Failed to process file {filename} due to: {str(e)}", current_file_dir)
                # Increment failed tracking counter
                self.failed_count += 1

        if self.target_files:
            Logger.log_process(
                "All single file tasks completed inside process pipeline.",
                os.path.dirname(self.target_files[0]) if self.target_files else "",
            )
        else:
            Logger.log_process("All tasks completed inside process pipeline.", self.folder_path)
