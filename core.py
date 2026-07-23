from utils import *
import os
import re
import time


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


def timecode_to_ms(tc_str):
    """Converts standard or negative SRT timecode string (HH:MM:SS,mmm or HH:MM:SS.mmm) to milliseconds."""
    tc_str = tc_str.strip()
    is_negative = False
    if tc_str.startswith("-"):
        is_negative = True
        tc_str = tc_str[1:]

    parts = re.split(r"[:,\.]", tc_str)
    if len(parts) >= 4:
        h, m, s, ms = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
        total_ms = (h * 3600 + m * 60 + s) * 1000 + ms
        return -total_ms if is_negative else total_ms
    return -1 if is_negative else 0


def ms_to_timecode(ms):
    """Converts milliseconds to standard SRT timecode string (HH:MM:SS,mmm)."""
    if ms < 0:
        ms = 0
    hours = ms // 3600000
    rem = ms % 3600000
    minutes = rem // 60000
    rem = rem % 60000
    seconds = rem // 1000
    millis = rem % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def parse_srt_blocks(lines):
    """Parses raw lines of an SRT file into a list of block dictionaries."""
    blocks = []
    tc_regex = re.compile(r"^(-?\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(-?\d{2}:\d{2}:\d{2}[,\.]\d{3})")
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        index_str = ""
        # Check if line is block index
        if line.isdigit() or (line.startswith("\ufeff") and line[1:].isdigit()):
            index_str = line
            i += 1
            if i >= n:
                break
            line = lines[i].strip()

        m = tc_regex.match(line)
        if m:
            start_str, end_str = m.group(1), m.group(2)
            start_ms = timecode_to_ms(start_str)
            end_ms = timecode_to_ms(end_str)

            i += 1
            text_lines = []
            while i < n:
                curr = lines[i]
                curr_stripped = curr.strip()
                if not curr_stripped:
                    break
                # Lookahead for next block index + timecode
                if (
                    curr_stripped.isdigit() or (curr_stripped.startswith("\ufeff") and curr_stripped[1:].isdigit())
                ) and (i + 1 < n and tc_regex.match(lines[i + 1].strip())):
                    break
                text_lines.append(curr.rstrip("\r\n"))
                i += 1

            blocks.append(
                {
                    "index": index_str,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "start_str": start_str,
                    "end_str": end_str,
                    "text_lines": text_lines,
                }
            )
        else:
            i += 1

    return blocks


class SubtitleProcessor:
    # Added target_files to handle single file process mode
    def __init__(self, folder_path, options=None, target_files=None):
        self.folder_path = folder_path
        self.options = options if options else {}
        self.target_files = target_files
        self.successful_count = 0
        self.failed_count = 0
        self.total_lines_processed = 0
        self.elapsed_time = 0

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
        empty_tag_pattern = re.compile(r"<([a-zA-Z1-6]+)\b[^>]*>\s*</\1>", re.IGNORECASE)

        start_time = time.time()
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
                    self.total_lines_processed += 1
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

                    # Option: Convert English Question Marks to Persian
                    if self.options.get("persian_question_mark", 1) and not is_timecode_or_index:
                        before_q = current_line
                        current_line = current_line.replace("?", "؟")
                        if current_line != before_q:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_q.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                log_msg = f'Line {index} modified | Option: Pre-Process Persian Question Mark | Before: "{b_clean}" -> After: "{c_clean}"'
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
                        # Skip lines that are just whitespace or empty
                        if not current_line.strip():
                            continue

                        # Only process if the line likely contains actual text
                        # Skip if the line contains only numbers and special characters/tags
                        if not any(c.isalpha() or "\u0600" <= c <= "\u06ff" for c in current_line):
                            continue

                        before_enum = current_line

                        def replace_eng_num(match):
                            return "".join(english_numerals.get(char, char) for char in match.group(0))

                        # Split text by HTML tags to preserve numbers inside tags
                        parts = re.split(r"(<[^>]+>)", current_line)
                        for i in range(len(parts)):
                            # Only process parts that are not HTML tags
                            if not parts[i].startswith("<"):
                                # Ensure numbers are not attached to English letters or other numbers on either side
                                parts[i] = re.sub(r"(?<![a-zA-Z0-9])(\d+)(?![a-zA-Z0-9])", replace_eng_num, parts[i])

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

                        # Option: Post-Process Remove Empty Tags
                        if self.options.get("remove_empty_tags", 1) and current_line:
                            before_tags = current_line
                            temp_line = current_line
                            while empty_tag_pattern.search(temp_line):
                                temp_line = empty_tag_pattern.sub("", temp_line)
                            current_line = temp_line
                            if current_line != before_tags:
                                file_has_changes = True
                                if self.options.get("detailed_subtitle_logs", 1):
                                    b_clean = before_tags.rstrip("\n")
                                    c_clean = current_line.rstrip("\n")
                                    log_msg = f'Line {index} modified | Option: Post-Process Remove Empty Tags | Before: "{b_clean}" -> After: "{c_clean}"'
                                    Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    # Finally, append the line if it wasn't removed completely
                    if current_line is not None:
                        processed_lines.append(current_line)

                # --- Block-Level Post-Process Operations ---
                if (
                    self.options.get("add_intro_credit", 0)
                    or self.options.get("remove_negative_timecodes", 1)
                    or self.options.get("remove_empty_subtitles", 1)
                    or self.options.get("reformat_renumber", 1)
                ):
                    blocks = parse_srt_blocks(processed_lines)

                    # Option: Add Intro Credit Subtitle
                    if self.options.get("add_intro_credit", 0):
                        credit_text = self.options.get("intro_credit_text", "").strip()
                        if credit_text:
                            credit_lines = [l.strip() for l in credit_text.split("\n") if l.strip()][:2]
                            if credit_lines:
                                try:
                                    dur_sec = int(self.options.get("intro_credit_duration", "8"))
                                    dur_sec = max(2, min(10, dur_sec))
                                except Exception:
                                    dur_sec = 8
                                dur_ms = dur_sec * 1000

                                first_start_ms = blocks[0]["start_ms"] if blocks else 86400000
                                if first_start_ms >= dur_ms:
                                    new_block = {
                                        "index": "1",
                                        "start_ms": 0,
                                        "end_ms": dur_ms,
                                        "start_str": ms_to_timecode(0),
                                        "end_str": ms_to_timecode(dur_ms),
                                        "text_lines": credit_lines,
                                    }
                                    blocks.insert(0, new_block)
                                    file_has_changes = True
                                    if self.options.get("detailed_subtitle_logs", 1):
                                        log_msg = f'Intro credit subtitle added at beginning | Timecode: "00:00:00,000 --> {ms_to_timecode(dur_ms)}"'
                                        Logger.log_subtitle_change(current_file_dir, filename, log_msg)
                                else:
                                    for k in range(len(blocks)):
                                        gap_start = blocks[k]["end_ms"]
                                        gap_end = (
                                            blocks[k + 1]["start_ms"]
                                            if (k + 1 < len(blocks))
                                            else (gap_start + dur_ms + 10000)
                                        )
                                        if gap_end - gap_start >= dur_ms:
                                            new_block = {
                                                "index": "",
                                                "start_ms": gap_start,
                                                "end_ms": gap_start + dur_ms,
                                                "start_str": ms_to_timecode(gap_start),
                                                "end_str": ms_to_timecode(gap_start + dur_ms),
                                                "text_lines": credit_lines,
                                            }
                                            blocks.insert(k + 1, new_block)
                                            file_has_changes = True
                                            if self.options.get("detailed_subtitle_logs", 1):
                                                log_msg = f'Intro credit subtitle added at gap after block {k + 1} | Timecode: "{ms_to_timecode(gap_start)} --> {ms_to_timecode(gap_start + dur_ms)}"'
                                                Logger.log_subtitle_change(current_file_dir, filename, log_msg)
                                            break

                    # Option: Remove Negative Timecodes
                    if self.options.get("remove_negative_timecodes", 1):
                        filtered_blocks = []
                        for b in blocks:
                            if (
                                b["start_ms"] < 0
                                or b["end_ms"] < 0
                                or b["start_str"].startswith("-")
                                or b["end_str"].startswith("-")
                            ):
                                file_has_changes = True
                                if self.options.get("detailed_subtitle_logs", 1):
                                    log_msg = f'Subtitle block removed | Option: Remove Negative Timecodes | Index: "{b["index"]}" | Timecode: "{b["start_str"]} --> {b["end_str"]}"'
                                    Logger.log_subtitle_change(current_file_dir, filename, log_msg)
                            else:
                                filtered_blocks.append(b)
                        blocks = filtered_blocks

                    # Option: Remove Empty Subtitles
                    if self.options.get("remove_empty_subtitles", 1):
                        filtered_blocks = []
                        for b in blocks:
                            text_content = "".join(b["text_lines"]).strip()
                            if not text_content:
                                file_has_changes = True
                                if self.options.get("detailed_subtitle_logs", 1):
                                    log_msg = f'Subtitle block removed | Option: Remove Empty Subtitles | Index: "{b["index"]}" | Timecode: "{b["start_str"]} --> {b["end_str"]}"'
                                    Logger.log_subtitle_change(current_file_dir, filename, log_msg)
                            else:
                                filtered_blocks.append(b)
                        blocks = filtered_blocks

                    # Option: Reformat & Renumber Subtitles
                    if self.options.get("reformat_renumber", 1):
                        reformatted_lines = []
                        for new_idx, b in enumerate(blocks, start=1):
                            reformatted_lines.append(f"{new_idx}\n")
                            tc_s = ms_to_timecode(b["start_ms"])
                            tc_e = ms_to_timecode(b["end_ms"])
                            reformatted_lines.append(f"{tc_s} --> {tc_e}\n")
                            for t_line in b["text_lines"]:
                                reformatted_lines.append(f"{t_line}\n")
                            reformatted_lines.append("\n")
                        processed_lines = reformatted_lines

                        if self.options.get("detailed_subtitle_logs", 1):
                            log_msg = f"Reformat & Renumber completed | Total blocks renumbered: {len(blocks)}"
                            Logger.log_subtitle_change(current_file_dir, filename, log_msg)

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

        self.elapsed_time = time.time() - start_time

        if self.target_files:
            Logger.log_process(
                "All single file tasks completed inside process pipeline.",
                os.path.dirname(self.target_files[0]) if self.target_files else "",
            )
        else:
            Logger.log_process("All tasks completed inside process pipeline.", self.folder_path)
