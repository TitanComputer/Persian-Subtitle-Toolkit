from utils import *
import os
import re


def build_flexible_regex(word):
    """
    Creates a regex pattern that ignores spaces, dots, zero-width non-joiners (\u200c)
    and kashida (ـ) between the characters of the provided word.
    Compiles with re.IGNORECASE to support case-insensitive English matching.
    """
    clean_word = re.sub(r"[\s\.\u200cـ\u064b-\u0652\u200b-\u200f\u202a-\u202e]", "", word)
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

    pattern = r"[\s\.\u200cـ\u064b-\u0652\u200b-\u200f\u202a-\u202e]*".join(char_patterns)
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

        for file_path in srt_files_paths:
            filename = os.path.basename(file_path)
            current_file_dir = os.path.dirname(file_path)

            # Define output directory path dynamically for the current file
            output_dir = os.path.join(current_file_dir, "Outputs")
            os.makedirs(output_dir, exist_ok=True)

            Logger.log_process(f"Identified file: {filename}", current_file_dir)

            try:
                # Read original file contents content safely
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                processed_lines = []
                file_has_changes = False

                if self.options.get("detailed_subtitle_logs", 1):
                    Logger.log_subtitle_change(current_file_dir, filename, f"Started tracking changes for: {filename}")

                for index, line in enumerate(lines, start=1):
                    original_line = line
                    current_line = original_line

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

                with open(output_file_path, "w", encoding="utf-8") as f:
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
