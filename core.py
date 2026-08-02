from utils import *
from rules import *
import os
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


# Helper function to trim spaces while preserving SRT line endings
def trim_line_spaces(line_text):
    if not line_text:
        return line_text
    stripped = line_text.strip()
    # Preserving structural carriage returns of SRT format
    if line_text.endswith("\r\n"):
        return stripped + "\r\n"
    elif line_text.endswith("\n"):
        return stripped + "\n"
    else:
        return stripped


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


def fix_inconsistent_dialog_hyphens(blocks):
    """Removes leading dialogue hyphens from multi-line blocks unless every line starts with one."""
    dialog_prefix_pattern = re.compile(
        r"""^(?P<prefix>(?:<[^<>]+>|[\s\u200b-\u200f\u202a-\u202e\ufeff])*)(?P<hyphen>-)\s*"""
    )

    for block in blocks:
        text_lines = block.get("text_lines", [])

        if len(text_lines) < 2:
            continue

        dialog_matches = [dialog_prefix_pattern.match(text_line) for text_line in text_lines]

        if all(dialog_matches):
            continue

        for line_index, dialog_match in enumerate(dialog_matches):
            if dialog_match:
                text_lines[line_index] = dialog_match.group("prefix") + text_lines[line_index][dialog_match.end() :]

    return blocks


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
            text_indices = []  # Added to track the original line numbers of pure subtitle texts
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
                text_indices.append(i + 1)  # Storing 1-based index to match enumerate
                i += 1

            blocks.append(
                {
                    "index": index_str,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "start_str": start_str,
                    "end_str": end_str,
                    "text_lines": text_lines,
                    "text_indices": text_indices,  # Included in block dictionary
                }
            )
        else:
            i += 1

    return blocks


def fix_trailing_dialog_hyphens(blocks):
    """Converts trailing dialogue hyphens to leading dialogue hyphens in multi-line dialogue blocks."""

    for block in blocks:
        text_lines = block.get("text_lines", [])

        if len(text_lines) < 2:
            continue

        all_end_with_hyphen = True
        any_start_with_hyphen = False

        for text_line in text_lines:
            stripped = text_line.strip()

            if not stripped.endswith("-"):
                all_end_with_hyphen = False
                break

            if stripped.startswith("-"):
                any_start_with_hyphen = True

        if not all_end_with_hyphen or any_start_with_hyphen:
            continue

        for line_index, text_line in enumerate(text_lines):
            stripped = text_line.rstrip()

            content = stripped[:-1].rstrip()

            if content:
                text_lines[line_index] = f"- {content}"

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
        # Pre-compile regexes for bypass list to optimize performance
        bypass_regexes = [(w, build_flexible_regex(w)) for w in bypass_list if build_flexible_regex(w)]

        remove_enabled = self.options.get("remove_enabled", 1)
        remove_list = [w.strip() for w in self.options.get("remove_list", "").split("\n") if w.strip()]
        # Pre-compile regexes for remove list to optimize performance
        remove_regexes = [(w, build_flexible_regex(w)) for w in remove_list if build_flexible_regex(w)]

        replace_enabled = self.options.get("replace_enabled", 1)
        replace_list = [w.strip() for w in self.options.get("replace_list", "").split("\n") if w.strip()]
        # Pre-compile regexes for replace list to optimize performance
        replace_regexes = [(w, build_flexible_regex(w)) for w in replace_list if build_flexible_regex(w)]

        post_trim_spaces = self.options.get("post_trim_spaces", 1)

        # Pre-compile heavy regex patterns used in line processing to avoid O(n) recompilation overhead
        zw_space = r"[\s\u200c\u200d\u200e\u200f\ufeff]"
        start_dot_pattern = re.compile(rf"^((?:{zw_space}|<[^>]+>)*)\.(?!{zw_space}*[.\-:;!?؟،,*~_|]){zw_space}*")
        end_dot_pattern = re.compile(
            rf"(?<![.\-:;!?؟،,*~_|\s\u200c\u200d\u200e\u200f\ufeff]){zw_space}*\.(?=(?:{zw_space}|</[^>]+>)*(?:\r\n|\n)?$)"
        )
        html_tag_split_pattern = re.compile(r"(<[^>]+>)")
        isolated_eng_num_pattern = re.compile(r"(?<![a-zA-Z0-9])(\d+)(?![a-zA-Z0-9])")

        start_time = time.time()
        for file_path in srt_files_paths:
            filename = os.path.basename(file_path)
            current_file_dir = os.path.dirname(file_path)

            # Define output directory path dynamically for the current file
            output_dir = os.path.join(current_file_dir, "Outputs")
            os.makedirs(output_dir, exist_ok=True)

            Logger.log_process(f"Identified file: {filename}", current_file_dir)

            try:
                # Smart encoding reader. Tries multiple encodings to handle UTF-16, UTF-8, ANSI, etc.
                encodings_to_try = ["utf-8", "utf-8-sig", "utf-16", "cp1256", "cp1252"]
                file_encoding = "utf-8"
                lines = []

                for enc in encodings_to_try:
                    try:
                        with open(file_path, "r", encoding=enc) as f:
                            lines = f.readlines()
                        file_encoding = enc
                        break
                    except UnicodeError:
                        continue
                else:
                    # Fallback if all fail
                    file_encoding = "utf-8"
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()

                Logger.log_process(f"Identified encoding: {file_encoding}", current_file_dir)

                # Pre-parse blocks to identify and isolate valid text lines from timecodes/indexes
                parsed_blocks_for_index = parse_srt_blocks(lines)
                valid_text_indices = set()
                for b in parsed_blocks_for_index:
                    valid_text_indices.update(b.get("text_indices", []))

                processed_lines = []
                file_has_changes = False

                if self.options.get("detailed_subtitle_logs", 1):
                    Logger.log_subtitle_change(current_file_dir, filename, f"Started tracking changes for: {filename}")

                for index, line in enumerate(lines, start=1):
                    self.total_lines_processed += 1

                    # Skip all processing if the line is not a subtitle text (e.g., timecodes, indexes, empty lines)
                    if index not in valid_text_indices:
                        processed_lines.append(line)
                        continue

                    original_line = line
                    current_line = original_line

                    # Check if line is standard subtitle timecode or index number
                    is_timecode_or_index = bool(
                        timecode_pattern.match(current_line) or index_pattern.match(current_line)
                    )

                    # Apply Pre-Process Option: Trim Spaces
                    if self.options.get("trim_spaces", 1):
                        current_line = trim_line_spaces(current_line)

                    # Log Pre-Process Changes
                    if current_line != original_line:
                        file_has_changes = True
                        if self.options.get("detailed_subtitle_logs", 1):
                            orig_clean = original_line.rstrip("\n")
                            curr_clean = current_line.rstrip("\n")
                            log_msg = f'Line {index} modified | Option: Pre-Process Trim Spaces | Before: "{orig_clean}" -> After: "{curr_clean}"'
                            Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    # Apply Pre-Process Option: Fix Abbreviations
                    if self.options.get("fix_abbreviations", 1) and not is_timecode_or_index:
                        before_abbr = current_line
                        temp_line = current_line

                        # Apply general English spaced abbreviations pattern
                        while english_abbr_pattern.search(temp_line):
                            temp_line = english_abbr_pattern.sub("", temp_line)

                        # Apply specific imported XML abbreviation rules
                        for rule_pattern, replace_with, is_regex in abbreviation_rules:
                            if is_regex:
                                temp_line = rule_pattern.sub(replace_with, temp_line)
                            else:
                                temp_line = temp_line.replace(rule_pattern, replace_with)

                        current_line = temp_line

                        if current_line != before_abbr:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_abbr.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                log_msg = f'Line {index} modified | Option: Pre-Process Fix Abbreviations | Before: "{b_clean}" -> After: "{c_clean}"'
                                Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    # Apply Pre-Process Option: Comma Fixes
                    if self.options.get("comma_fixes", 1) and not is_timecode_or_index:
                        before_comma = current_line
                        temp_line = current_line

                        for rule_pattern, replace_with, is_regex in comma_rules_list:
                            if is_regex:
                                temp_line = rule_pattern.sub(replace_with, temp_line)
                            else:
                                temp_line = temp_line.replace(rule_pattern, replace_with)

                        current_line = temp_line

                        if current_line != before_comma:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_comma.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                log_msg = f'Line {index} modified | Option: Pre-Process Comma Fixes | Before: "{b_clean}" -> After: "{c_clean}"'
                                Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    # Apply Pre-Process Option: Exclamation Mark Fixes
                    if self.options.get("exclamation_fixes", 1) and not is_timecode_or_index:
                        before_excl = current_line
                        temp_line = current_line

                        for rule_pattern, replace_with, is_regex in exclamation_rules_list:
                            if is_regex:
                                temp_line = rule_pattern.sub(replace_with, temp_line)
                            else:
                                temp_line = temp_line.replace(rule_pattern, replace_with)

                        current_line = temp_line

                        if current_line != before_excl:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_excl.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                log_msg = f'Line {index} modified | Option: Pre-Process Exclamation Mark Fixes | Before: "{b_clean}" -> After: "{c_clean}"'
                                Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    # Apply Pre-Process Option: Parentheses Fixes
                    if self.options.get("parentheses_fixes", 1) and not is_timecode_or_index:
                        before_paren = current_line
                        temp_line = current_line

                        for rule_pattern, replace_with, is_regex in parentheses_rules_list:
                            if is_regex:
                                temp_line = rule_pattern.sub(replace_with, temp_line)
                            else:
                                temp_line = temp_line.replace(rule_pattern, replace_with)

                        current_line = temp_line

                        if current_line != before_paren:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_paren.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                log_msg = f'Line {index} modified | Option: Pre-Process Parentheses Fixes | Before: "{b_clean}" -> After: "{c_clean}"'
                                Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    # Apply Pre-Process Option: Question Mark Fixes
                    if self.options.get("question_mark_fixes", 1) and not is_timecode_or_index:
                        before_qm = current_line
                        temp_line = current_line

                        for rule_pattern, replace_with, is_regex in question_mark_rules_list:
                            if is_regex:
                                temp_line = rule_pattern.sub(replace_with, temp_line)
                            else:
                                temp_line = temp_line.replace(rule_pattern, replace_with)

                        current_line = temp_line

                        if current_line != before_qm:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_qm.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                log_msg = f'Line {index} modified | Option: Pre-Process Question Mark Fixes | Before: "{b_clean}" -> After: "{c_clean}"'
                                Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    # Double-Quotes Fixes processing and logging
                    if self.options.get("double_quotes_fixes", 1) == 1 and not is_timecode_or_index:
                        before_dq = current_line
                        temp_line = current_line
                        for rule_pattern, replace_with, is_regex in double_quotes_rules_list:
                            if is_regex:
                                temp_line = rule_pattern.sub(replace_with, temp_line)
                            else:
                                temp_line = temp_line.replace(rule_pattern, replace_with)

                        # Handle unbalanced double quotes (odd number of quotes)
                        if temp_line.count('"') % 2 != 0:
                            # Replace the quote and any surrounding spaces/tabs with a single space
                            # to avoid merging words. The unneeded_spaces rules will clean up any extra spaces.
                            temp_line = re.sub(r'[ \t]*"[ \t]*', " ", temp_line)

                        current_line = temp_line
                        if current_line != before_dq:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_dq.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                Logger.log_subtitle_change(
                                    current_file_dir,
                                    filename,
                                    f'Line {index} modified | Option: Pre-Process Double-Quotes Fixes | Before: "{b_clean}" -> After: "{c_clean}"',
                                )

                    # Dash Fixes processing and logging
                    if self.options.get("dash_fixes", 1) == 1 and not is_timecode_or_index:
                        before_dash = current_line
                        temp_line = current_line
                        for rule_pattern, replace_with, is_regex in dash_rules_list:
                            if is_regex:
                                temp_line = rule_pattern.sub(replace_with, temp_line)
                            else:
                                temp_line = temp_line.replace(rule_pattern, replace_with)
                        current_line = temp_line
                        if current_line != before_dash:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_dash.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                Logger.log_subtitle_change(
                                    current_file_dir,
                                    filename,
                                    f'Line {index} modified | Option: Pre-Process Dash Fixes | Before: "{b_clean}" -> After: "{c_clean}"',
                                )

                    # Comments Fixes processing and logging
                    if self.options.get("comments_fixes", 1) == 1 and not is_timecode_or_index:
                        before_com = current_line
                        temp_line = current_line
                        for rule_pattern, replace_with, is_regex in comments_rules_list:
                            if is_regex:
                                temp_line = rule_pattern.sub(replace_with, temp_line)
                            else:
                                temp_line = temp_line.replace(rule_pattern, replace_with)
                        current_line = temp_line
                        if current_line != before_com:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_com.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                Logger.log_subtitle_change(
                                    current_file_dir,
                                    filename,
                                    f'Line {index} modified | Option: Pre-Process Comments Fixes | Before: "{b_clean}" -> After: "{c_clean}"',
                                )

                    # Dialog Hyphen Fix processing and logging
                    if self.options.get("dialog_hyphen_fix", 1) == 1 and not is_timecode_or_index:
                        before_dh = current_line
                        temp_line = current_line
                        for rule_pattern, replace_with, is_regex in dialog_hyphen_fix_list:
                            if is_regex:
                                temp_line = rule_pattern.sub(replace_with, temp_line)
                            else:
                                temp_line = temp_line.replace(rule_pattern, replace_with)
                        current_line = temp_line
                        if current_line != before_dh:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_dh.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                Logger.log_subtitle_change(
                                    current_file_dir,
                                    filename,
                                    f'Line {index} modified | Option: Pre-Process Dialog Hyphen Fix | Before: "{b_clean}" -> After: "{c_clean}"',
                                )

                    # Apply Pre-Process Option: Remove Standalone Dots
                    if self.options.get("remove_standalone_dots", 1) and not is_timecode_or_index:
                        before_dots = current_line

                        # Whitespace + Zero-Width & Invisible Formatting Characters (\u200c=ZWNJ, \u200d=ZWJ, \u200e=LRM, \u200f=RLM, \ufeff=BOM)
                        # Regex patterns are pre-compiled outside the main loop for performance

                        # Remove standalone dot at the start of the line (ignores HTML tags & zero-width chars prefix)
                        current_line = start_dot_pattern.sub(r"\1", current_line)

                        # Remove standalone dot at the end of the line (ignores HTML tags & zero-width chars suffix)
                        current_line = end_dot_pattern.sub("", current_line)

                        if current_line != before_dots:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_dots.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                log_msg = f'Line {index} modified | Option: Pre-Process Remove Standalone Dots | Before: "{b_clean}" -> After: "{c_clean}"'
                                Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    # Apply Pre-Process Option: Remove Unneeded Spaces (Aligned with XML rules)
                    if self.options.get("remove_unneeded_spaces", 1) and not is_timecode_or_index:
                        before_unneeded = current_line
                        temp_line = current_line

                        for pattern, replacement, desc in unneeded_rules:
                            temp_line = pattern.sub(replacement, temp_line)

                        current_line = temp_line

                        if current_line != before_unneeded:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_unneeded.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                log_msg = f'Line {index} modified | Option: Pre-Process Remove Unneeded Spaces | Before: "{b_clean}" -> After: "{c_clean}"'
                                Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    # Option: Convert English Question Marks and Commas to Persian
                    if self.options.get("persian_question_mark_and_comma", 1) and not is_timecode_or_index:
                        before_q = current_line
                        current_line = current_line.replace("?", "؟")
                        current_line = current_line.replace(",", "،")
                        if current_line != before_q:
                            file_has_changes = True
                            if self.options.get("detailed_subtitle_logs", 1):
                                b_clean = before_q.rstrip("\n")
                                c_clean = current_line.rstrip("\n")
                                log_msg = f'Line {index} modified | Option: Pre-Process Persian Question Mark and Comma | Before: "{b_clean}" -> After: "{c_clean}"'
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
                        parts = html_tag_split_pattern.split(current_line)
                        for i in range(len(parts)):
                            # Only process parts that are not HTML tags
                            if not parts[i].startswith("<"):
                                # Ensure numbers are not attached to English letters or other numbers on either side
                                parts[i] = isolated_eng_num_pattern.sub(replace_eng_num, parts[i])

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
                        for word, reg in bypass_regexes:
                            if reg.search(current_line):
                                is_bypassed = True
                                if self.options.get("detailed_subtitle_logs", 1):
                                    log_msg = f'Line {index} bypassed | Matched "{word}" in Bypass List. No further process changes applied.'
                                    Logger.log_subtitle_change(current_file_dir, filename, log_msg)
                                break

                    if not is_bypassed:
                        is_removed = False

                        # Process Option: Remove List
                        if remove_enabled:
                            for word, reg in remove_regexes:
                                if reg.search(current_line):
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
                            for word, reg in replace_regexes:
                                if reg.search(current_line):
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
                            current_line = trim_line_spaces(current_line)

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

                # --- Block-Level Dialog Hyphen Validation ---
                if self.options.get("dialog_hyphen_fix", 1) == 1:
                    dialog_blocks = parse_srt_blocks(processed_lines)
                    dialog_blocks = fix_trailing_dialog_hyphens(dialog_blocks)
                    dialog_blocks = fix_inconsistent_dialog_hyphens(dialog_blocks)

                    dialog_reformatted_lines = []
                    for dialog_block in dialog_blocks:
                        if dialog_block["index"]:
                            dialog_reformatted_lines.append(f'{dialog_block["index"]}\n')
                        dialog_reformatted_lines.append(f'{dialog_block["start_str"]} --> {dialog_block["end_str"]}\n')
                        for dialog_text_line in dialog_block["text_lines"]:
                            dialog_reformatted_lines.append(f"{dialog_text_line}\n")
                        dialog_reformatted_lines.append("\n")

                    if dialog_reformatted_lines:
                        processed_lines = dialog_reformatted_lines

                # --- Block-Level Post-Process Operations ---
                if (
                    self.options.get("add_intro_credit", 0)
                    or self.options.get("remove_negative_timecodes", 1)
                    or self.options.get("remove_empty_subtitles", 1)
                    or self.options.get("reformat_renumber", 1)
                ):
                    blocks = parse_srt_blocks(processed_lines)

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
                                    b_index = b["index"]
                                    b_start = b["start_str"]
                                    b_end = b["end_str"]
                                    log_msg = f'Subtitle block removed | Option: Remove Negative Timecodes | Index: "{b_index}" | Timecode: "{b_start} --> {b_end}"'
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
                                    b_index = b["index"]
                                    b_start = b["start_str"]
                                    b_end = b["end_str"]
                                    log_msg = f'Subtitle block removed | Option: Remove Empty Subtitles | Index: "{b_index}" | Timecode: "{b_start} --> {b_end}"'
                                    Logger.log_subtitle_change(current_file_dir, filename, log_msg)
                            else:
                                filtered_blocks.append(b)
                        blocks = filtered_blocks

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
                                required_space = dur_ms + 400

                                if not blocks:
                                    new_block = {
                                        "index": "1",
                                        "start_ms": 200,
                                        "end_ms": 200 + dur_ms,
                                        "start_str": ms_to_timecode(200),
                                        "end_str": ms_to_timecode(200 + dur_ms),
                                        "text_lines": credit_lines,
                                    }
                                    blocks.append(new_block)
                                    file_has_changes = True
                                    if self.options.get("detailed_subtitle_logs", 1):
                                        log_msg = f'Intro credit subtitle added | Timecode: "{ms_to_timecode(200)} --> {ms_to_timecode(200 + dur_ms)}"'
                                        Logger.log_subtitle_change(current_file_dir, filename, log_msg)
                                else:
                                    first_start_ms = blocks[0]["start_ms"]
                                    if first_start_ms >= required_space:
                                        start_time_ms = 200
                                        end_time_ms = start_time_ms + dur_ms
                                        new_block = {
                                            "index": "1",
                                            "start_ms": start_time_ms,
                                            "end_ms": end_time_ms,
                                            "start_str": ms_to_timecode(start_time_ms),
                                            "end_str": ms_to_timecode(end_time_ms),
                                            "text_lines": credit_lines,
                                        }
                                        blocks.insert(0, new_block)
                                        file_has_changes = True
                                        if self.options.get("detailed_subtitle_logs", 1):
                                            log_msg = f'Intro credit subtitle added at beginning | Timecode: "{ms_to_timecode(start_time_ms)} --> {ms_to_timecode(end_time_ms)}"'
                                            Logger.log_subtitle_change(current_file_dir, filename, log_msg)
                                    else:
                                        inserted = False
                                        for k in range(len(blocks) - 1):
                                            gap_start = blocks[k]["end_ms"]
                                            gap_end = blocks[k + 1]["start_ms"]

                                            if gap_end - gap_start >= required_space:
                                                start_time_ms = gap_start + 200
                                                end_time_ms = start_time_ms + dur_ms
                                                new_block = {
                                                    "index": "",
                                                    "start_ms": start_time_ms,
                                                    "end_ms": end_time_ms,
                                                    "start_str": ms_to_timecode(start_time_ms),
                                                    "end_str": ms_to_timecode(end_time_ms),
                                                    "text_lines": credit_lines,
                                                }
                                                blocks.insert(k + 1, new_block)
                                                inserted = True
                                                file_has_changes = True
                                                if self.options.get("detailed_subtitle_logs", 1):
                                                    log_msg = f'Intro credit subtitle added at gap after block {k + 1} | Timecode: "{ms_to_timecode(start_time_ms)} --> {ms_to_timecode(end_time_ms)}"'
                                                    Logger.log_subtitle_change(current_file_dir, filename, log_msg)
                                                break

                                        if not inserted:
                                            last_end = blocks[-1]["end_ms"]
                                            start_time_ms = last_end + 200
                                            end_time_ms = start_time_ms + dur_ms
                                            new_block = {
                                                "index": "",
                                                "start_ms": start_time_ms,
                                                "end_ms": end_time_ms,
                                                "start_str": ms_to_timecode(start_time_ms),
                                                "end_str": ms_to_timecode(end_time_ms),
                                                "text_lines": credit_lines,
                                            }
                                            blocks.append(new_block)
                                            file_has_changes = True
                                            if self.options.get("detailed_subtitle_logs", 1):
                                                log_msg = f'Intro credit subtitle added at the end | Timecode: "{ms_to_timecode(start_time_ms)} --> {ms_to_timecode(end_time_ms)}"'
                                                Logger.log_subtitle_change(current_file_dir, filename, log_msg)

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

                # Option: Post-Process Force RTL (Remove control chars and force Right-To-Left)
                # Executed after reformat and renumber block as requested
                if self.options.get("force_rtl", 1):
                    rtl_processed_lines = []
                    rtl_modified_lines_count = 0

                    # Remove specific control characters
                    ctrl_chars = ["\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e"]

                    # Tuples of symbols that require RTL enforcement at boundaries
                    start_symbols = (
                        ".",
                        "…",
                        "-",
                        "–",
                        "—",
                        '"',
                        "'",
                        "«",
                        "»",
                        "“",
                        "”",
                        "‘",
                        "’",
                        "(",
                        "[",
                        "{",
                        "<",
                    )
                    end_symbols = (
                        ".",
                        "!",
                        "؟",
                        "?",
                        "،",
                        ",",
                        ":",
                        "؛",
                        ";",
                        "…",
                        '"',
                        "'",
                        "«",
                        "»",
                        "“",
                        "”",
                        "‘",
                        "’",
                        ")",
                        "]",
                        "}",
                        ">",
                    )

                    for index, line in enumerate(processed_lines, start=1):
                        if index_pattern.match(line) or timecode_pattern.match(line) or not line.strip():
                            rtl_processed_lines.append(line)
                        else:
                            original_text_line = line
                            clean_text = line

                            for char in ctrl_chars:
                                clean_text = clean_text.replace(char, "")

                            # Apply RTL Trim Spaces
                            if post_trim_spaces and clean_text:
                                before_post = clean_text
                                clean_text = trim_line_spaces(clean_text)
                                if before_post != clean_text:
                                    file_has_changes = True
                                    if self.options.get("detailed_subtitle_logs", 1):
                                        before_clean = before_post.rstrip("\n")
                                        curr_clean = clean_text.rstrip("\n")
                                        log_msg = f'Line {index} modified | Option: RTL Trim Spaces | Before: "{before_clean}" -> After: "{curr_clean}"'
                                        Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                            # Apply Post-Process Option: Smart RTL Enforcement
                            if clean_text.strip():
                                line_stripped = clean_text.rstrip("\r\n")
                                line_ending = clean_text[len(line_stripped) :]

                                # Remove HTML tags AND invisible zero-width chars temporarily to check boundaries accurately
                                text_no_tags = re.sub(r"<[^>]+>", "", line_stripped)
                                text_no_tags = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text_no_tags).strip()

                                if text_no_tags:
                                    # Check if the line contains any non-ASCII (non-English) characters
                                    has_non_english = bool(re.search(r"[^\x00-\x7F]", text_no_tags))

                                    if has_non_english:
                                        # Fix visually typed punctuation at the start of the line
                                        # Moves misplaced punctuation (colons, question/exclamation marks) from the start to the end
                                        if re.match(r"^((?:<[^>]+>\s*)*)([:؛!\?؟])", line_stripped):
                                            line_stripped = re.sub(
                                                r"^((?:<[^>]+>\s*)*)([:؛!\?؟])\s*(.*)$", r"\1\3\2", line_stripped
                                            )

                                            # Re-evaluate text_no_tags after modification
                                            text_no_tags = re.sub(r"<[^>]+>", "", line_stripped)
                                            text_no_tags = re.sub(
                                                r"[\u200b\u200c\u200d\ufeff]", "", text_no_tags
                                            ).strip()

                                        has_symbol_start = text_no_tags.startswith(start_symbols)
                                        has_symbol_end = text_no_tags.endswith(end_symbols)
                                        has_english_or_digits = bool(re.search(r"[a-zA-Z0-9]", text_no_tags))

                                        rtl_line = line_stripped

                                        # Use RLE (\u202b) and PDF (\u202c) to strictly enforce RTL direction
                                        # This forces the internal bidi algorithm to treat English words and digits as embedded inside an RTL context
                                        if has_symbol_start or has_symbol_end or has_english_or_digits:
                                            rtl_line = "\u202b" + rtl_line + "\u202c"

                                        clean_text = rtl_line + line_ending
                                    else:
                                        # Skip RTL processing completely for fully English/ASCII lines
                                        clean_text = line_stripped + line_ending
                                else:
                                    clean_text = line_stripped + line_ending

                            if clean_text != original_text_line:
                                file_has_changes = True
                                if self.options.get("detailed_subtitle_logs", 1):
                                    before_clean = original_text_line.rstrip("\n")
                                    curr_clean = clean_text.rstrip("\n")
                                    log_msg = f'Line {index} modified | Option: Smart RTL Enforcement | Before: "{before_clean}" -> After: "{curr_clean}"'
                                    Logger.log_subtitle_change(current_file_dir, filename, log_msg)
                                rtl_modified_lines_count += 1

                            rtl_processed_lines.append(clean_text)

                    # Log total RTL changes once at the end if any lines were modified
                    if rtl_modified_lines_count > 0 and self.options.get("detailed_subtitle_logs", 1):
                        log_msg = f"Total subtitle lines RTL formatted: {rtl_modified_lines_count}"
                        Logger.log_subtitle_change(current_file_dir, filename, log_msg)

                    processed_lines = rtl_processed_lines

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
