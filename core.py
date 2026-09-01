from concurrent.futures import ProcessPoolExecutor, as_completed, wait, FIRST_COMPLETED
import multiprocessing

from converter import *

_PROCESS_WORKER_OPTIONS = None
_PROCESS_PROGRESS_QUEUE = None


def _init_process_worker(options, progress_queue=None):
    global _PROCESS_WORKER_OPTIONS, _PROCESS_PROGRESS_QUEUE
    _PROCESS_WORKER_OPTIONS = options
    _PROCESS_PROGRESS_QUEUE = progress_queue


def _process_file_in_worker(file_path):
    processor = SubtitleProcessor(
        "",
        options=_PROCESS_WORKER_OPTIONS or {},
        target_files=[file_path],
        _worker_mode=True,
        progress_queue=_PROCESS_PROGRESS_QUEUE,
        progress_file_path=file_path,
    )
    return processor.run()


def _extract_required_literal(pattern):
    """Extracts a conservative mandatory literal prefix from a regex pattern."""
    pattern_text = getattr(pattern, "pattern", "")
    if not pattern_text.startswith(r"\b"):
        return None

    cursor = 2
    if cursor < len(pattern_text) and pattern_text[cursor] == "(":
        cursor += 1

    literal_chars = []
    while cursor < len(pattern_text):
        char = pattern_text[cursor]
        if char in "()[]{}|*+?\\.^$":
            break
        literal_chars.append(char)
        cursor += 1

    literal = "".join(literal_chars)
    return literal or None


def _prepare_rule_fast_paths(rule_list):
    """Adds safe literal guards to regex rules without changing rule order."""
    prepared_rules = []
    for rule_pattern, replace_with, is_regex in rule_list:
        required_literal = _extract_required_literal(rule_pattern) if is_regex else rule_pattern
        prepared_rules.append((rule_pattern, replace_with, is_regex, required_literal))
    return prepared_rules


# Precompute safe literal guards for the largest rule groups.
SPACE_TO_INVISIBLE_SPACE_FAST_RULES = _prepare_rule_fast_paths(space_to_invisible_space_rules)
HEXRE_FAST_RULES = _prepare_rule_fast_paths(hexre_rules_list)

HTML_TAG_RE = re.compile(r"<[^>]+>")
ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")
MUSIC_SYMBOLS_RE = re.compile(r"[♪♬♫]")
ALIGNMENT_TAG_RE = re.compile(r"\{\\[aA][nN][1-9]\}")

ARABIC_CHAR_TRANS = str.maketrans(arabic_to_persian_chars)
ARABIC_NUM_TRANS = str.maketrans(arabic_numerals)
CTRL_CHAR_TRANS = str.maketrans("", "", "\u200e\u200f\u202a\u202b\u202c\u202d\u202e")


def _log_change(index, opt_name, before, after, logs_buffer, detailed_logs_enabled):
    """Standardized logger to keep subtitle tracking uniform and DRY."""
    if detailed_logs_enabled and before != after:
        b_clean = before.rstrip("\n")
        c_clean = after.rstrip("\n")
        logs_buffer.append(f"Line {index} modified | Option: {opt_name} | Before: |{b_clean}| -> After: |{c_clean}|")


def apply_rule_set(text, rules):
    """Applies mixed regex/literal rules."""
    for rule_pattern, replace_with, is_regex in rules:
        if is_regex:
            text = rule_pattern.sub(replace_with, text)
        else:
            text = text.replace(rule_pattern, replace_with)
    return text


class TimestampedLogBuffer(list):
    def append(self, message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        super().append((timestamp, message))


def fix_misplaced_timecodes(blocks, logs_buffer, detailed_logs_enabled):
    """Removes empty blocks and reorders blocks chronologically by start time."""
    valid_blocks = []
    for block in blocks:
        # Check if block has any non-empty text lines
        has_text = any(line.strip() for line in block.get("text_lines", []))
        if not has_text:
            if detailed_logs_enabled:
                logs_buffer.append(
                    f"Block {block.get('index', '')} removed | Option: Fix Misplaced Timecodes | Before: |{block.get('start_str')} --> {block.get('end_str')}| -> After: |[Deleted Empty Block]|"
                )
        else:
            valid_blocks.append(block)

    # Check if the remaining blocks are out of chronological order
    is_out_of_order = False
    for i in range(1, len(valid_blocks)):
        if valid_blocks[i]["start_ms"] < valid_blocks[i - 1]["start_ms"]:
            is_out_of_order = True
            break

    if is_out_of_order:
        # Stable sort based on start time
        sorted_blocks = sorted(valid_blocks, key=lambda b: b["start_ms"])
        if detailed_logs_enabled:
            logs_buffer.append("Option: Fix Misplaced Timecodes | Blocks were reordered chronologically.")
        return sorted_blocks

    return valid_blocks


def remove_duplicate_subtitles(blocks, logs_buffer, detailed_logs_enabled):
    """Removes duplicate subtitle blocks that have identical timecodes and text."""
    seen = set()
    duplicate_counts = {}
    filtered_blocks = []

    for block in blocks:
        # Create a unique key using exact timecodes and text content
        key = (block["start_str"], block["end_str"], tuple(block["text_lines"]))

        if key in seen:
            duplicate_counts[key] = duplicate_counts.get(key, 0) + 1
        else:
            seen.add(key)
            filtered_blocks.append(block)

    if detailed_logs_enabled:
        for key, count in duplicate_counts.items():
            b_start, b_end, _ = key
            logs_buffer.append(
                f'Duplicate subtitles removed | Option: Remove Duplicate Subtitles | Timecode: "{b_start} --> {b_end}" | {count} duplicate(s) deleted.'
            )

    return filtered_blocks


def fix_overlapping_timecodes(blocks, logs_buffer, detailed_logs_enabled):
    """
    Fixes timecode overlaps.
    1. If two adjacent blocks start at the exact same time, merges them into a single block
       spanning the maximum end time to prevent 0ms zero-duration subtitles.
    2. For standard sequential overlaps, adjusts the end time of the preceding block to 1ms before the next block's start.
    """
    if not blocks:
        return blocks, False

    has_changes = False
    merged_blocks = []
    i = 0

    while i < len(blocks):
        current_block = blocks[i]

        # Handle blocks starting at the exact same timestamp
        while i + 1 < len(blocks) and blocks[i + 1]["start_ms"] == current_block["start_ms"]:
            next_block = blocks[i + 1]
            old_end_ms = current_block["end_ms"]
            old_end_str = current_block["end_str"]

            # Merge text lines
            current_block["text_lines"].extend(next_block["text_lines"])

            # Expand duration to cover the maximum end time of both blocks
            if next_block["end_ms"] > current_block["end_ms"]:
                current_block["end_ms"] = next_block["end_ms"]
                current_block["end_str"] = next_block["end_str"]

            has_changes = True
            if detailed_logs_enabled:
                logs_buffer.append(
                    f'Coincident blocks merged | Option: Fix Overlapping Timecodes | Merged Block {next_block.get("index", "")} into Block {current_block.get("index", "")} | Timecode: "{current_block["start_str"]} --> {current_block["end_str"]}"'
                )

            i += 1

        merged_blocks.append(current_block)
        i += 1

    # Fix standard sequential overlaps on the merged blocks list
    for j in range(len(merged_blocks) - 1):
        curr_b = merged_blocks[j]
        next_b = merged_blocks[j + 1]

        if curr_b["end_ms"] >= next_b["start_ms"]:
            old_end_str = curr_b["end_str"]
            new_end_ms = max(curr_b["start_ms"], next_b["start_ms"] - 1)

            if curr_b["end_ms"] != new_end_ms:
                curr_b["end_ms"] = new_end_ms
                curr_b["end_str"] = ms_to_timecode(new_end_ms)
                has_changes = True

                if detailed_logs_enabled:
                    logs_buffer.append(
                        f'Timecode overlap fixed | Option: Fix Overlapping Timecodes | Block {curr_b.get("index", "")} | Before: "{curr_b["start_str"]} --> {old_end_str}" -> After: "{curr_b["start_str"]} --> {curr_b["end_str"]}"'
                    )

    # Re-index blocks sequentially
    for new_index, b in enumerate(merged_blocks, start=1):
        b["index"] = str(new_index)

    return merged_blocks, has_changes


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


def is_pure_english(text):
    """
    Checks if the given text line is purely English (contains no Persian/Arabic characters).
    Ignores music symbols and HTML tags to evaluate text content accurately.
    """
    # Ignore music symbols and HTML tags to check if the text is purely English
    clean_for_check = re.sub(r"[♪♫<i>b/\\<>]", "", text)
    return not bool(re.search(r"[\u0600-\u06FF]", clean_for_check))


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


def fix_inconsistent_dialog_hyphens(blocks):
    """Removes leading dialogue hyphens from multi-line blocks unless every line starts with one."""
    dialog_prefix_pattern = re.compile(
        r"""^(?P<prefix>(?:<[^<>]+>|[\s\u200b-\u200f\u202a-\u202e\ufeff♪♫♭♯])*)(?P<hyphen>-)\s*"""
    )

    for block in blocks:
        text_lines = block.get("text_lines", [])
        # Preserve dialogue blocks that still contain trailing dialogue markers
        if any(text_line.strip().endswith("-") for text_line in text_lines):
            continue

        if len(text_lines) == 1:
            dialog_match = dialog_prefix_pattern.match(text_lines[0])

            if dialog_match:
                prefix = dialog_match.group("prefix")
                remainder = text_lines[0][dialog_match.end() :]
                # Split single-line inline dialogues into two lines if a second dialogue hyphen exists
                inline_match = re.search(r"^(.*?[\.،!؟\s])\s*-\s*(.*)$", remainder)
                if inline_match:
                    first_part = inline_match.group(1).rstrip()
                    # Remove single trailing dot while preserving ellipsis (...)
                    if first_part.endswith(".") and not first_part.endswith(".."):
                        first_part = first_part[:-1].rstrip()

                    second_part = inline_match.group(2).lstrip()

                    # Move misplaced leading ellipsis from second dialogue part to the end
                    has_leading_ellipsis = False
                    if second_part.startswith("...") or second_part.startswith("…"):
                        has_leading_ellipsis = True
                        second_part = re.sub(r"^(\.{3,}|…)\s*", "", second_part)

                    first_line = f"{prefix}- {first_part}"
                    if has_leading_ellipsis:
                        second_line = f"- {second_part.rstrip()}..."
                    else:
                        second_line = f"- {second_part}"

                    block["text_lines"] = [first_line, second_line]
                else:
                    text_lines[0] = f"{prefix}{remainder}"

            continue

        dialog_matches = [dialog_prefix_pattern.match(text_line) for text_line in text_lines]

        if all(dialog_matches):
            continue

        for line_index, dialog_match in enumerate(dialog_matches):
            if dialog_match:
                text_lines[line_index] = dialog_match.group("prefix") + text_lines[line_index][dialog_match.end() :]

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
    def __init__(
        self,
        folder_path,
        options=None,
        target_files=None,
        progress_callback=None,
        convert_start_callback=None,
        process_start_callback=None,
        complete_callback=None,
        _worker_mode=False,
        progress_queue=None,
        progress_file_path=None,
    ):
        self.folder_path = folder_path
        self.options = options if options else {}
        self.target_files = target_files

        self.progress_callback = progress_callback
        self.convert_start_callback = convert_start_callback
        self.process_start_callback = process_start_callback
        self.complete_callback = complete_callback
        self._worker_mode = _worker_mode
        self._deferred_process_logs = []
        self._progress_queue = progress_queue
        self._progress_file_path = progress_file_path
        self._progress_queue = progress_queue
        self._progress_file_path = progress_file_path

        self.successful_count = 0
        self.failed_count = 0
        self.total_lines_processed = 0
        self.elapsed_time = 0

        self.total_input_lines = 0
        self.last_progress_reported = -1
        self._progress_lock = threading.Lock()
        self._counter_lock = threading.Lock()
        self._log_lock = threading.Lock()

    def _report_convert_start(self):
        if self.convert_start_callback:
            try:
                self.convert_start_callback()
            except Exception:
                pass

    def _report_process_start(self):
        if self.process_start_callback:
            try:
                self.process_start_callback()
            except Exception:
                pass

    def _report_progress(self):
        if not self.progress_callback:
            return

        with self._progress_lock:
            if self.total_input_lines <= 0:
                return

            percent = min(100.0, (self.total_lines_processed / self.total_input_lines) * 100)

            if percent == self.last_progress_reported:
                return

            self.last_progress_reported = percent

        try:
            self.progress_callback(percent)
        except Exception:
            pass

    @staticmethod
    def _count_file_lines(file_path):
        try:
            with open(file_path, "rb") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def _report_worker_line_progress(self, processed_lines):
        if not self._worker_mode or self._progress_queue is None or not self._progress_file_path:
            return
        try:
            self._progress_queue.put((self._progress_file_path, processed_lines))
        except Exception:
            pass

    @staticmethod
    def _count_file_lines(file_path):
        try:
            with open(file_path, "rb") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def _report_worker_line_progress(self, processed_lines):
        if not self._worker_mode or self._progress_queue is None or not self._progress_file_path:
            return
        try:
            self._progress_queue.put((self._progress_file_path, processed_lines))
        except Exception:
            pass

    @staticmethod
    def _get_worker_count(file_count):
        if file_count <= 0:
            return 1

        cpu_count = os.cpu_count() or 1
        max_workers = min(8, max(1, cpu_count))
        return min(file_count, max_workers)

    @staticmethod
    def _should_parallelize(file_paths):
        file_count = len(file_paths)
        if file_count < 3:
            return False

        total_size = 0
        for path in file_paths:
            try:
                total_size += os.path.getsize(path)
            except OSError:
                total_size += 1

        # Avoid process startup overhead for a few very small files while still
        # parallelizing large batches and CPU-heavy workloads.
        return file_count >= 8 or total_size >= 512 * 1024

    def _report_progress_by_completed_weight(self, completed_weight, total_weight):
        if not self.progress_callback or total_weight <= 0:
            return

        percent = min(100.0, (completed_weight / total_weight) * 100.0)
        self.progress_callback(percent)

    def _report_complete(self):
        if self.complete_callback:
            try:
                self.complete_callback()
            except Exception:
                pass

    def run(self):
        # Determine files to process based on execution mode
        valid_extensions = (".srt", ".txt", ".vtt", ".ass")

        if self.target_files:
            srt_files_paths = [f for f in self.target_files if f.lower().endswith(valid_extensions)]
            if srt_files_paths and not self._worker_mode:
                Logger.log_process(
                    f"Single file process started. Found {len(srt_files_paths)} file(s).",
                    os.path.dirname(srt_files_paths[0]),
                )
        else:
            if not self.folder_path or not os.path.isdir(self.folder_path):
                return
            all_files = os.listdir(self.folder_path)
            srt_files_paths = [
                os.path.join(self.folder_path, f) for f in all_files if f.lower().endswith(valid_extensions)
            ]
            if not srt_files_paths:
                Logger.log_process(
                    "No valid subtitle files (.srt, .txt, .vtt, .ass) found to process.", self.folder_path
                )
                return
            Logger.log_process(f"Process started. Found {len(srt_files_paths)} file(s).", self.folder_path)

        # Cache ALL options to avoid thousands of dictionary lookups during line processing
        opt_bypass_enabled = self.options.get("bypass_enabled", 1)
        opt_remove_enabled = self.options.get("remove_enabled", 1)
        opt_replace_enabled = self.options.get("replace_enabled", 1)

        opt_remove_alignment_tags = self.options.get("remove_alignment_tags", 1)
        opt_trim_spaces = self.options.get("trim_spaces", 1)
        opt_fix_misplaced_chars = self.options.get("fix_misplaced_chars", 1)
        opt_fix_abbreviations = self.options.get("fix_abbreviations", 1)
        opt_comma_fixes = self.options.get("comma_fixes", 1)
        opt_exclamation_fixes = self.options.get("exclamation_fixes", 1)
        opt_parentheses_fixes = self.options.get("parentheses_fixes", 1)
        opt_question_mark_fixes = self.options.get("question_mark_fixes", 1)
        opt_double_quotes_fixes = self.options.get("double_quotes_fixes", 1) == 1
        opt_dash_fixes = self.options.get("dash_fixes", 1) == 1
        opt_comments_fixes = self.options.get("comments_fixes", 1) == 1
        opt_dialog_hyphen_fix = self.options.get("dialog_hyphen_fix", 1) == 1
        opt_remove_standalone_dots = self.options.get("remove_standalone_dots", 1)
        opt_remove_unneeded_spaces = self.options.get("remove_unneeded_spaces", 1)
        opt_persian_question_mark_and_comma = self.options.get("persian_question_mark_and_comma", 1)
        opt_arabic_char_to_persian = self.options.get("arabic_char_to_persian", 1)
        opt_arabic_num_to_persian = self.options.get("arabic_num_to_persian", 1)
        opt_english_num_to_persian = self.options.get("english_num_to_persian", 1)
        opt_space_to_invisible_space = self.options.get("space_to_invisible_space", 1)
        opt_hexre_fixes = self.options.get("hexre_fixes", 1)
        opt_add_missing_spaces = self.options.get("add_missing_spaces", 1)

        opt_post_trim_spaces = self.options.get("post_trim_spaces", 1)
        opt_remove_empty_tags = self.options.get("remove_empty_tags", 1)
        opt_remove_negative_timecodes = self.options.get("remove_negative_timecodes", 1)
        opt_fix_misplaced_timecodes = self.options.get("fix_misplaced_timecodes", 1)
        opt_remove_duplicate_subtitles = self.options.get("remove_duplicate_subtitles", 1)
        opt_fix_overlapping_timecodes = self.options.get("fix_overlapping_timecodes", 1)
        opt_remove_empty_subtitles = self.options.get("remove_empty_subtitles", 1)
        opt_add_intro_credit = self.options.get("add_intro_credit", 0)
        opt_reformat_renumber = self.options.get("reformat_renumber", 1)
        opt_force_rtl = self.options.get("force_rtl", 1)
        opt_encode_utf8 = self.options.get("encode_utf8", 1)
        opt_delete_original = self.options.get("delete_original", 0)
        detailed_logs_enabled = self.options.get("detailed_subtitle_logs", 1)
        opt_convert_ass_comments = self.options.get("convert_ass_comments", 0)
        opt_delete_converted_temp_files = self.options.get("delete_converted_temp_files", 0)

        # Extract Process configuration variables
        bypass_list = [w.strip() for w in self.options.get("bypass_list", "").split("\n") if w.strip()]
        # Pre-compile regexes for bypass list to optimize performance
        bypass_regexes = []
        for w in bypass_list:
            regex = build_flexible_regex(w)
            if regex:
                bypass_regexes.append((w, regex))

        remove_list = [w.strip() for w in self.options.get("remove_list", "").split("\n") if w.strip()]
        # Pre-compile regexes for remove list to optimize performance
        remove_regexes = []
        for w in remove_list:
            regex = build_flexible_regex(w)
            if regex:
                remove_regexes.append((w, regex))

        replace_list = [w.strip() for w in self.options.get("replace_list", "").split("\n") if w.strip()]
        # Pre-compile regexes for replace list to optimize performance
        replace_regexes = []
        for w in replace_list:
            regex = build_flexible_regex(w)
            if regex:
                replace_regexes.append((w, regex))

        start_time = time.time()
        use_parallel = self._should_parallelize(srt_files_paths)
        self._report_convert_start()

        # Parallel workers report progress by completed files, so the parent does not need
        # to pre-convert and pre-scan every file before starting the CPU-bound work.
        if not self._worker_mode and not use_parallel:
            converted_files = []

            for file_path in srt_files_paths:

                actual_file_path, validation_success = process_and_convert_if_needed(
                    file_path,
                    TimestampedLogBuffer(),
                    TimestampedLogBuffer(),
                    False,
                    opt_convert_ass_comments,
                )

                if validation_success:
                    converted_files.append(actual_file_path)

            self.total_input_lines = 0

            for converted_file in converted_files:
                try:
                    with open(converted_file, "r", encoding="utf-8", errors="ignore") as f:
                        self.total_input_lines += sum(1 for _ in f)
                except Exception:
                    pass

        self._report_process_start()
        max_workers = self._get_worker_count(len(srt_files_paths))

        def _process_file(file_path):
            filename = os.path.basename(file_path)
            current_file_dir = os.path.dirname(file_path)

            # Define output directory path dynamically for the current file
            output_dir = os.path.join(current_file_dir, "Outputs")
            os.makedirs(output_dir, exist_ok=True)
            # Initialize timestamped log buffers for the current file to aggregate disk I/O
            file_process_logs = TimestampedLogBuffer()
            file_subtitle_logs = TimestampedLogBuffer()
            file_has_changes = False
            actual_file_path = file_path
            converted_temp_file = False
            local_lines_processed = 0
            worker_progress_interval = 0

            file_process_logs.append(f"Identified file: {filename}")

            # Check and convert alternative formats before reading
            actual_file_path, validation_success = process_and_convert_if_needed(
                file_path,
                file_process_logs,
                file_subtitle_logs,
                detailed_logs_enabled,
                opt_convert_ass_comments,
            )

            converted_temp_file = validation_success and actual_file_path != file_path

            if not validation_success:
                file_process_logs.append(f"Validation failed for unsupported or corrupted format: {filename}")
                self._report_progress()
                with self._counter_lock:
                    self.failed_count += 1
                return  # Skip processing for this invalid file

            try:
                # Smart encoding reader on actual_file_path instead of original file_path
                encodings_to_try = ["utf-8", "utf-8-sig", "utf-16", "cp1256", "cp1252"]
                file_encoding = "utf-8"
                lines = []

                for enc in encodings_to_try:
                    try:
                        with open(actual_file_path, "r", encoding=enc) as f:  # Use actual_file_path here
                            lines = f.readlines()
                        file_encoding = enc
                        break
                    except UnicodeError:
                        continue
                else:
                    # Fallback if all fail
                    file_encoding = "utf-8"
                    with open(
                        actual_file_path, "r", encoding="utf-8", errors="ignore"
                    ) as f:  # Use actual_file_path here
                        lines = f.readlines()

                file_process_logs.append(f"Identified encoding: {file_encoding}")

                # Pre-parse blocks to identify and isolate valid text lines from timecodes/indexes
                parsed_blocks_for_index = parse_srt_blocks(lines)
                valid_text_indices = set()
                for b in parsed_blocks_for_index:
                    valid_text_indices.update(b.get("text_indices", []))

                processed_lines = []
                parentheses_fixed_lines = {}

                if self._worker_mode:
                    worker_progress_interval = max(1, (len(lines) + 999) // 1000)

                if detailed_logs_enabled:
                    file_subtitle_logs.append(f"Started tracking changes for: {filename}")

                timecode_match = timecode_pattern.match
                index_match = index_pattern.match

                for index, line in enumerate(lines, start=1):
                    local_lines_processed += 1
                    if local_lines_processed >= 50:
                        with self._counter_lock:
                            self.total_lines_processed += local_lines_processed
                            reported_lines = self.total_lines_processed
                        local_lines_processed = 0
                        self._report_progress()
                        self._report_worker_line_progress(reported_lines)

                    # Skip all processing if the line is not a subtitle text (e.g., timecodes, indexes, empty lines)
                    if index not in valid_text_indices:
                        processed_lines.append(line)
                        continue

                    original_line = line
                    current_line = parentheses_fixed_lines.pop(index, original_line)
                    line_is_pure_english = is_pure_english(current_line)

                    # Check if line is standard subtitle timecode or index number
                    is_timecode_or_index = bool(timecode_match(current_line) or index_match(current_line))

                    # Apply Pre-Process Option: Remove Alignment Tags
                    # Fast path guard: Check for '{' and 'an'/'AN'
                    if opt_remove_alignment_tags and "{" in current_line and "an" in current_line.lower():
                        before_align = current_line
                        current_line = ALIGNMENT_TAG_RE.sub("", current_line)

                        if current_line != before_align:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Remove Alignment Tags",
                                before_align,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Apply Pre-Process Option: Trim Spaces
                    if opt_trim_spaces:
                        current_line = trim_line_spaces(current_line)

                    # Log Pre-Process Changes
                    if current_line != original_line:
                        file_has_changes = True
                        _log_change(
                            index,
                            "Pre-Process Trim Spaces",
                            original_line,
                            current_line,
                            file_subtitle_logs,
                            detailed_logs_enabled,
                        )

                    # Skip text processing entirely for timecode or index lines
                    if is_timecode_or_index:
                        processed_lines.append(current_line)
                        continue

                    # Option: Fix Misplaced Chars processing and logging
                    # Fast path guard: Check if common punctuation exists before running rules.
                    if opt_fix_misplaced_chars and any(c in current_line for c in "*:؛!?؟.,،-»«…"):
                        before_misplaced = current_line
                        temp_line = current_line

                        # Preserve and strip trailing newline to prevent regexes from corrupting line endings
                        line_ending = ""
                        if temp_line.endswith(("\r\n", "\n")):
                            if temp_line.endswith("\r\n"):
                                line_ending = "\r\n"
                            else:
                                line_ending = "\n"
                            temp_line = temp_line[: -len(line_ending)]

                        if not misplaced_chars_comment_pattern.fullmatch(temp_line):
                            temp_line = apply_rule_set(temp_line, misplaced_chars_rules)

                        temp_line += line_ending
                        current_line = temp_line

                        if current_line != before_misplaced:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Fix Misplaced Chars",
                                before_misplaced,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Apply Pre-Process Option: Fix Abbreviations
                    if opt_fix_abbreviations:
                        before_abbr = current_line
                        temp_line = current_line

                        # Apply general English spaced abbreviations pattern
                        while english_abbr_pattern.search(temp_line):
                            temp_line = english_abbr_pattern.sub("", temp_line)

                        # Apply specific imported XML abbreviation rules
                        temp_line = apply_rule_set(temp_line, abbreviation_rules)

                        current_line = temp_line

                        if current_line != before_abbr:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Fix Abbreviations",
                                before_abbr,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Apply Pre-Process Option: Comma Fixes
                    # Fast path guard: Check if line contains any comma format.
                    if opt_comma_fixes and any(c in current_line for c in ",،"):
                        before_comma = current_line
                        temp_line = current_line

                        # Apply comma rules only if the line is not purely English
                        if not line_is_pure_english:
                            temp_line = apply_rule_set(temp_line, comma_rules_list)
                        else:
                            # Remove only a trailing comma from pure English lines without changing internal commas
                            temp_line = re.sub(
                                r"[،,]\s*(?=(?:[\u202A-\u202E\u200E\u200F]|[\"'»”’\)\]\}]|<[^<>]+>)*\s*$)",
                                "",
                                temp_line,
                            )

                        current_line = temp_line

                        if current_line != before_comma:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Comma Fixes",
                                before_comma,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Apply Pre-Process Option: Exclamation Mark Fixes
                    # Fast path guard: Check for literal exclamation mark.
                    if opt_exclamation_fixes and "!" in current_line:
                        before_excl = current_line
                        temp_line = current_line

                        temp_line = apply_rule_set(temp_line, exclamation_rules_list)

                        current_line = temp_line

                        if current_line != before_excl:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Exclamation Mark Fixes",
                                before_excl,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Apply Pre-Process Option: Parentheses Fixes
                    # Fast path guard: Check for standard bracket types.
                    if (
                        opt_parentheses_fixes
                        and any(c in current_line for c in "()[]{}")
                        and index not in parentheses_fixed_lines
                    ):
                        before_paren = current_line
                        temp_line = current_line

                        # Normalize repeated brackets before any other parentheses processing.
                        # This prevents repeated brackets from interfering with cross-line handling.
                        temp_line = re.sub(
                            r"(\(|\[|\{)(?:[ \t\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]*(?:\1))+",
                            r"\1",
                            temp_line,
                        )

                        # Normalize repeated opening brackets at the start of the visible text.
                        # This keeps leading HTML/bidi markers intact while fixing cases like:
                        # "((text" -> "(text)"
                        leading_prefix_match = re.match(
                            r"^(?:[ \t\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]+|<[^>]+>)*",
                            temp_line,
                        )
                        leading_prefix = leading_prefix_match.group(0) if leading_prefix_match else ""
                        body = temp_line[len(leading_prefix) :]

                        handled_cross_line = False
                        bracket_pairs = {
                            "(": ")",
                            "[": "]",
                            "{": "}",
                        }
                        reverse_bracket_pairs = {value: key for key, value in bracket_pairs.items()}

                        # Handle misplaced brackets that span two subtitle lines.
                        # This must be checked before the single-line fallback because each subtitle line is processed separately.
                        next_index = index + 1
                        has_valid_next = (
                            next_index in valid_text_indices
                            and next_index < len(lines) + 1
                            and next_index not in parentheses_fixed_lines
                        )
                        next_line = lines[next_index - 1] if has_valid_next else ""

                        if has_valid_next and next_line:
                            next_body_match = re.match(
                                r"^(?:[ \t\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]+|<[^>]+>)*",
                                next_line,
                            )
                            next_prefix = next_body_match.group(0) if next_body_match else ""
                            next_line_ending = (
                                "\r\n" if next_line.endswith("\r\n") else "\n" if next_line.endswith("\n") else ""
                            )
                            next_body = next_line[len(next_prefix) :].rstrip("\r\n")
                            current_line_ending = (
                                "\r\n" if temp_line.endswith("\r\n") else "\n" if temp_line.endswith("\n") else ""
                            )
                            current_body = body.rstrip("\r\n")

                            if current_body and next_body:
                                current_last_bracket = next(
                                    (char for char in reversed(current_body) if char in reverse_bracket_pairs),
                                    None,
                                )
                                next_first_bracket = next_body[0]

                                if (
                                    current_last_bracket in reverse_bracket_pairs
                                    and current_body.endswith(current_last_bracket)
                                    and next_first_bracket == reverse_bracket_pairs[current_last_bracket]
                                ):
                                    opening_char = reverse_bracket_pairs[current_last_bracket]
                                    closing_char = current_last_bracket
                                    current_body = current_body[:-1]
                                    next_body = next_body[1:]

                                    # Move the misplaced brackets to the outside of the two-line subtitle.
                                    current_line_fixed = (
                                        leading_prefix + opening_char + current_body + current_line_ending
                                    )

                                    # Keep the closing bracket inside trailing HTML tags so the bracket remains part of the styled text.
                                    trailing_html_match = re.search(
                                        r"((?:<[^<>]+>|[\u200e\u200f\u202a-\u202e\u2066-\u2069\u061c\ufeff\u200b]|[ \t])+)$",
                                        next_body,
                                    )
                                    if trailing_html_match:
                                        trailing_html = trailing_html_match.group(1)
                                        next_content = next_body[: -len(trailing_html)]
                                        next_line_fixed = (
                                            next_prefix + next_content + closing_char + trailing_html + next_line_ending
                                        )
                                    else:
                                        next_line_fixed = next_prefix + next_body + closing_char + next_line_ending

                                    current_line_fixed = apply_rule_set(current_line_fixed, parentheses_rules_list)
                                    next_line_fixed = apply_rule_set(next_line_fixed, parentheses_rules_list)

                                    current_line = current_line_fixed
                                    parentheses_fixed_lines[next_index] = next_line_fixed
                                    handled_cross_line = True

                                    if current_line != before_paren:
                                        file_has_changes = True
                                        _log_change(
                                            index,
                                            "Pre-Process Parentheses Fixes",
                                            before_paren,
                                            current_line,
                                            file_subtitle_logs,
                                            detailed_logs_enabled,
                                        )

                                    if next_line_fixed != next_line:
                                        file_has_changes = True
                                        _log_change(
                                            next_index,
                                            "Pre-Process Parentheses Fixes",
                                            next_line,
                                            next_line_fixed,
                                            file_subtitle_logs,
                                            detailed_logs_enabled,
                                        )

                                    temp_line = current_line

                        if body and not handled_cross_line:
                            first_char = body[0]
                            if first_char in bracket_pairs:
                                closing_char = bracket_pairs[first_char]

                                # Collapse repeated opening brackets, allowing invisible RTL marks/spaces between them.
                                body = re.sub(
                                    rf"^(?:{re.escape(first_char)}(?:[ \t\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]*{re.escape(first_char)})+)",
                                    first_char,
                                    body,
                                )

                                # Detect a misplaced opening bracket at the start when another opening bracket appears later.
                                # In this structure, the leading bracket belongs to the sentence ending and the later bracket
                                # starts the actual parenthesized phrase. Move the leading bracket to the end of the line.
                                has_matching_bracket_in_next = bool(
                                    has_valid_next and next_line and closing_char in next_line
                                )

                                if (
                                    closing_char not in body
                                    and first_char in body[1:]
                                    and not has_matching_bracket_in_next
                                ):
                                    body = body[1:]

                                    line_ending = ""
                                    if body.endswith("\r\n"):
                                        line_ending = "\r\n"
                                        body = body[:-2]
                                    elif body.endswith("\n"):
                                        line_ending = "\n"
                                        body = body[:-1]

                                    body = body + closing_char + line_ending

                                # If the line has no matching closing bracket and is not completed on the next line, append one at the end.
                                if closing_char not in body and not has_matching_bracket_in_next:
                                    line_ending = ""

                                    if body.endswith("\r\n"):
                                        line_ending = "\r\n"
                                        body = body[:-2]
                                    elif body.endswith("\n"):
                                        line_ending = "\n"
                                        body = body[:-1]

                                    body = body + closing_char + line_ending

                            temp_line = leading_prefix + body

                            temp_line = apply_rule_set(temp_line, parentheses_rules_list)

                            current_line = temp_line

                        if current_line != before_paren and not handled_cross_line:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Parentheses Fixes",
                                before_paren,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Apply Pre-Process Option: Question Mark Fixes
                    # Fast path guard: Check for English or Arabic question mark.
                    if opt_question_mark_fixes and ("?" in current_line or "؟" in current_line):
                        before_qm = current_line
                        temp_line = current_line

                        temp_line = apply_rule_set(temp_line, question_mark_rules_list)

                        current_line = temp_line

                        if current_line != before_qm:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Question Mark Fixes",
                                before_qm,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Double-Quotes Fixes processing and logging
                    # Fast path guard: Check for double quotes existence.
                    if opt_double_quotes_fixes and '"' in current_line:
                        before_dq = current_line
                        temp_line = current_line
                        temp_line = apply_rule_set(temp_line, double_quotes_rules_list)

                        # Handle misplaced opening quote at start of line
                        if temp_line.count('"') == 2:
                            line_ending = ""

                            if temp_line.endswith("\r\n"):
                                line_ending = "\r\n"
                                temp_line = temp_line[:-2]
                            elif temp_line.endswith("\n"):
                                line_ending = "\n"
                                temp_line = temp_line[:-1]

                            # Detect leading HTML tags, dashes, spaces, and RTL/LTR control marks
                            html_prefix_match = re.match(
                                r"^((?:<[^<>]+>|[\u200e\u200f\u202a-\u202e\u2066-\u2069\u061c\ufeff\u200b]|[\s\.\-–—])*)",
                                temp_line,
                            )
                            html_prefix = html_prefix_match.group(1) if html_prefix_match else ""
                            remainder = temp_line[len(html_prefix) :]

                            # Detect trailing HTML tags, spaces, and RTL/LTR control marks
                            html_suffix_match = re.search(
                                r"((?:<[^<>]+>|[\u200e\u200f\u202a-\u202e\u2066-\u2069\u061c\ufeff\u200b]|\s)+)$",
                                remainder,
                            )
                            if html_suffix_match:
                                html_suffix = html_suffix_match.group(1)
                                content_after_html = remainder[: -len(html_suffix)]
                            else:
                                html_suffix = ""
                                content_after_html = remainder

                            if content_after_html.count('"') == 2:
                                # Case 1: Both quotes are clustered at the start (""Text -> "Text")
                                if content_after_html.startswith('""'):
                                    content_after_html = '"' + content_after_html[2:] + '"'

                                # Case 2: Both quotes are clustered at the end (Text"" -> "Text")
                                elif content_after_html.endswith('""'):
                                    content_after_html = '"' + content_after_html[:-2] + '"'

                                else:
                                    q1_idx = content_after_html.find('"')
                                    q2_idx = content_after_html.rfind('"')

                                    # Special Guard: Skip if q1 is an opening quote preceded by punctuation or space (e.g. '- حالا،"برت"', 'گفت: "سلام"')
                                    prev_char_q1 = content_after_html[q1_idx - 1] if q1_idx > 0 else ""
                                    is_q1_opening_quote = prev_char_q1 in " \t\u200c\u200e\u200f([{'«،,;:.!?-–—"

                                    # Case 3: Misplaced closing quote pushed to the beginning of line in RTL text
                                    if q1_idx == 0 and q2_idx < len(content_after_html) - 1:
                                        prev_char = content_after_html[q2_idx - 1] if q2_idx > 0 else ""
                                        next_char = (
                                            content_after_html[q2_idx + 1]
                                            if q2_idx + 1 < len(content_after_html)
                                            else ""
                                        )
                                        if (
                                            prev_char in " \t\u200c\u200e\u200f([{'«،,;:.!?-–—"
                                            and next_char not in " \t\r\n"
                                        ):
                                            content_after_html = content_after_html[1:] + '"'

                                    # Case 4: Misplaced opening quote pushed to the end of the line
                                    # Active only when q1 closes a word early in the sentence and is NOT an opening quote
                                    elif q1_idx > 0 and q2_idx > q1_idx and not is_q1_opening_quote:
                                        next_char_q1 = (
                                            content_after_html[q1_idx + 1]
                                            if q1_idx + 1 < len(content_after_html)
                                            else ""
                                        )
                                        after_q2 = content_after_html[q2_idx + 1 :]

                                        # q1 must strictly be attached to a word and followed by a space
                                        is_q1_attached_word = (
                                            prev_char_q1.isalnum() or "\u0600" <= prev_char_q1 <= "\u06ff"
                                        ) and next_char_q1 in " \t"

                                        # q2 must be at the end of the line (optionally followed by terminal punctuation)
                                        is_q2_trailing = after_q2.strip("!؟?.،,;: \t") == ""

                                        if is_q1_attached_word and is_q2_trailing:
                                            content_after_html = (
                                                '"' + content_after_html[:q2_idx] + content_after_html[q2_idx + 1 :]
                                            )

                            temp_line = html_prefix + content_after_html + html_suffix + line_ending

                        # Handle unbalanced double quotes (odd number of quotes)
                        if temp_line.count('"') % 2 != 0:
                            # Replace the quote and any surrounding spaces/tabs with a single space
                            # to avoid merging words. The unneeded_spaces rules will clean up any extra spaces.
                            temp_line = re.sub(r'[ \t]*"[ \t]*', " ", temp_line)

                        current_line = temp_line
                        if current_line != before_dq:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Double-Quotes Fixes",
                                before_dq,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Dash Fixes processing and logging
                    # Fast path guard: Check for standard dash variations.
                    if opt_dash_fixes and any(c in current_line for c in "-–—"):
                        before_dash = current_line
                        temp_line = current_line
                        temp_line = apply_rule_set(temp_line, dash_rules_list)
                        current_line = temp_line
                        if current_line != before_dash:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Dash Fixes",
                                before_dash,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Comments Fixes processing and logging
                    # Fast path guard: Subtitle comments typically involve brackets.
                    if opt_comments_fixes and any(c in current_line for c in ":."):
                        before_com = current_line
                        temp_line = current_line
                        temp_line = apply_rule_set(temp_line, comments_rules_list)
                        current_line = temp_line
                        if current_line != before_com:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Comments Fixes",
                                before_com,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Dialog Hyphen Fix processing and logging
                    if opt_dialog_hyphen_fix:
                        before_dh = current_line
                        temp_line = current_line
                        temp_line = apply_rule_set(temp_line, dialog_hyphen_fix_list)
                        current_line = temp_line
                        if current_line != before_dh:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Dialog Hyphen Fix",
                                before_dh,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Apply Pre-Process Option: Remove Standalone Dots
                    # Fast path guard: Requires at least one period.
                    if opt_remove_standalone_dots and any(c in current_line for c in ".…"):
                        before_dots = current_line

                        # Whitespace + Zero-Width & Invisible Formatting Characters (\u200c=ZWNJ, \u200d=ZWJ, \u200e=LRM, \u200f=RLM, \ufeff=BOM)
                        # Regex patterns are pre-compiled outside the main loop for performance

                        # Remove standalone dot at the start of the line (ignores HTML tags, zero-width chars, quotes & music symbols prefix)
                        current_line = start_dot_pattern.sub(r"\1\2", current_line)

                        # Remove standalone dot at the end of the line (ignores HTML tags, zero-width chars, quotes & music symbols suffix)
                        current_line = end_dot_pattern.sub("", current_line)

                        if current_line != before_dots:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Remove Standalone Dots",
                                before_dots,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Apply Pre-Process Option: Remove Unneeded Spaces (Aligned with XML rules)
                    # Fast path guard: Requires at least one space or tab character.
                    if opt_remove_unneeded_spaces and any(c in current_line for c in " \n\t"):
                        # Skip space cleaning for subtitle comment lines with open/close markers
                        # Updated regex to support both single and double colons (e.g., .: :. or ..:: ::..)
                        if not re.search(r"\.{1,2}:{1,2}.*?:{1,2}\.{1,2}", current_line):
                            temp_line = current_line

                            for pattern, replacement, desc in unneeded_rules:
                                step_before = temp_line
                                temp_line = pattern.sub(replacement, temp_line)

                                if temp_line != step_before:
                                    file_has_changes = True
                                    _log_change(
                                        index,
                                        "Pre-Process Remove Unneeded Spaces",
                                        step_before,
                                        temp_line,
                                        file_subtitle_logs,
                                        detailed_logs_enabled,
                                    )

                            current_line = temp_line

                    # Option: Convert English Question Marks and Commas to Persian
                    # Fast path guard: Look for target English characters before attempting translation.
                    if opt_persian_question_mark_and_comma and ("?" in current_line or "," in current_line):
                        before_q = current_line
                        current_line = current_line.replace("?", "؟")

                        if not line_is_pure_english:
                            current_line = current_line.replace(",", "،")

                        if current_line != before_q:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Persian Question Mark and Comma",
                                before_q,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # 1. Convert Arabic Characters to Persian
                    if opt_arabic_char_to_persian and any(c in current_line for c in "يكةؤإأ"):
                        before_char = current_line
                        current_line = current_line.translate(ARABIC_CHAR_TRANS)
                        if current_line != before_char:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Arabic Chars",
                                before_char,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # 2. Convert Arabic Numerals to Persian Numerals
                    if opt_arabic_num_to_persian and any(c in current_line for c in "٠١٢٣٤٥٦٧٨٩"):
                        before_anum = current_line
                        current_line = current_line.translate(ARABIC_NUM_TRANS)
                        if current_line != before_anum:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Arabic Numerals",
                                before_anum,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # 3. Convert English Numerals to Persian Numerals conditionally
                    if opt_english_num_to_persian and any(c in current_line for c in "1234567890"):
                        # Skip lines that are just whitespace or empty
                        if not current_line.strip():
                            continue

                        # Only process if the line likely contains actual text
                        # Skip if the line contains only numbers and special characters/tags
                        if not any(c.isalpha() or "\u0600" <= c <= "\u06ff" for c in current_line):
                            continue

                        before_enum = current_line

                        def replace_eng_num(match):
                            start = match.start()
                            end = match.end()
                            text = match.string

                            # Expand left boundary across alphanumeric and common identifier/date delimiters
                            left = start
                            while left > 0 and re.match(r"[A-Za-z0-9@._\-+/\\:]", text[left - 1]):
                                left -= 1

                            # Expand right boundary across alphanumeric and common identifier/date delimiters
                            right = end
                            while right < len(text) and re.match(r"[A-Za-z0-9@._\-+/\\:]", text[right]):
                                right += 1

                            token = text[left:right]

                            # Skip emails, usernames, identifiers, filenames, dates with English month names, and mixed English tokens
                            if re.search(r"[A-Za-z]", token):
                                return match.group(0)

                            # Check preceding context across whitespace/delimiters for English terms (e.g., "Init 5", "Windows 11", "Part 2")
                            preceding_text = text[:start].rstrip(" \t._-/:")
                            if re.search(r"[A-Za-z]+$", preceding_text):
                                return match.group(0)

                            # Check following context across whitespace/delimiters for English terms (e.g., "5 GHz", "5 MB", "5 Star")
                            following_text = text[end:].lstrip(" \t._-/:")
                            if re.search(r"^[A-Za-z]+", following_text):
                                return match.group(0)

                            return "".join(english_numerals.get(char, char) for char in match.group(0))

                        # Split text by HTML tags to preserve numbers inside tags
                        parts = html_tag_split_pattern.split(current_line)
                        for i in range(len(parts)):
                            # Only process parts that are not HTML tags
                            if not parts[i].startswith("<"):
                                # Ensure numbers are not attached to English letters or identifier-like tokens
                                parts[i] = isolated_eng_num_pattern.sub(replace_eng_num, parts[i])

                        current_line = "".join(parts)
                        if current_line != before_enum:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process English Numerals",
                                before_enum,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # 4. Convert Space to Invisible Space conditionally
                    if opt_space_to_invisible_space:
                        before_space_zwnj = current_line
                        temp_line = current_line

                        for (
                            rule_pattern,
                            replace_with,
                            is_regex,
                            required_literal,
                        ) in SPACE_TO_INVISIBLE_SPACE_FAST_RULES:
                            if required_literal is not None and required_literal not in temp_line:
                                continue
                            if is_regex:
                                temp_line = rule_pattern.sub(replace_with, temp_line)
                            else:
                                temp_line = temp_line.replace(rule_pattern, replace_with)

                        current_line = temp_line
                        if current_line != before_space_zwnj:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Space to Invisible Space",
                                before_space_zwnj,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # 5. Fix Common Hexre Typo Errors conditionally
                    if opt_hexre_fixes and any(c in current_line for c in "ههٔهٕ"):
                        before_hexre = current_line
                        temp_line = current_line

                        for rule_pattern, replace_with, is_regex, required_literal in HEXRE_FAST_RULES:
                            if required_literal is not None and required_literal not in temp_line:
                                continue
                            if is_regex:
                                temp_line = rule_pattern.sub(replace_with, temp_line)
                            else:
                                temp_line = temp_line.replace(rule_pattern, replace_with)

                        current_line = temp_line
                        if current_line != before_hexre:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Hexre Typo Fixes",
                                before_hexre,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Apply Pre-Process Option: Add Missing Spaces
                    if opt_add_missing_spaces:
                        before_add_missing_spaces = current_line
                        temp_line = add_missing_spaces(current_line)
                        current_line = temp_line

                        if current_line != before_add_missing_spaces:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Pre-Process Add Missing Spaces",
                                before_add_missing_spaces,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # --- Process Options ---
                    is_bypassed = False
                    if opt_bypass_enabled and bypass_regexes:
                        for word, reg in bypass_regexes:
                            if reg.search(current_line):
                                is_bypassed = True
                                if detailed_logs_enabled:
                                    log_msg = f'Line {index} bypassed | Matched "{word}" in Bypass List. No further process changes applied.'
                                    file_subtitle_logs.append(log_msg)
                                break

                    if not is_bypassed:
                        is_removed = False

                        # Process Option: Remove List
                        if opt_remove_enabled and remove_regexes:
                            for word, reg in remove_regexes:
                                if reg.search(current_line):
                                    is_removed = True
                                    file_has_changes = True
                                    if detailed_logs_enabled:
                                        curr_clean = current_line.rstrip("\n")
                                        log_msg = f'Line {index} removed | Matched "{word}" in Remove List. Entire line deleted. The line was: "{curr_clean}"'
                                        file_subtitle_logs.append(log_msg)
                                    current_line = None
                                    break

                        # If removed, skip remaining processing steps and do not append this line
                        if is_removed:
                            continue

                        # Process Option: Replace List
                        if opt_replace_enabled and replace_regexes:
                            for word, reg in replace_regexes:
                                if reg.search(current_line):
                                    before_replace = current_line
                                    current_line = reg.sub("", current_line)
                                    if current_line != before_replace:
                                        file_has_changes = True
                                        _log_change(
                                            index,
                                            f'Replace List (Matched "{word}")',
                                            before_replace,
                                            current_line,
                                            file_subtitle_logs,
                                            detailed_logs_enabled,
                                        )
                    # --- Post-Process Options ---
                    # Apply Post-Process Option: Trim Spaces
                    if opt_post_trim_spaces and current_line:
                        before_post = current_line
                        current_line = trim_line_spaces(current_line)

                        if current_line != before_post:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Post-Process Trim Spaces",
                                before_post,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Option: Post-Process Remove Empty Tags
                    # Fast path guard: Subtitle tags inherently require < and > characters.
                    if opt_remove_empty_tags and any(c in current_line for c in "<>"):
                        before_tags = current_line
                        temp_line = current_line
                        while empty_tag_pattern.search(temp_line):
                            temp_line = empty_tag_pattern.sub("", temp_line)
                        current_line = temp_line
                        if current_line != before_tags:
                            file_has_changes = True
                            _log_change(
                                index,
                                "Post-Process Remove Empty Tags",
                                before_tags,
                                current_line,
                                file_subtitle_logs,
                                detailed_logs_enabled,
                            )

                    # Finally, append the line if it wasn't removed completely
                    if current_line is not None:
                        processed_lines.append(current_line)

                # --- Block-Level Dialog Hyphen Validation ---
                if opt_dialog_hyphen_fix:
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
                    opt_add_intro_credit
                    or opt_remove_negative_timecodes
                    or opt_fix_misplaced_timecodes
                    or opt_remove_duplicate_subtitles
                    or opt_remove_empty_subtitles
                    or opt_reformat_renumber
                ):
                    blocks = parse_srt_blocks(processed_lines)

                    # Option: Remove Negative Timecodes
                    if opt_remove_negative_timecodes:
                        filtered_blocks = []
                        for b in blocks:
                            if (
                                b["start_ms"] < 0
                                or b["end_ms"] < 0
                                or b["start_str"].startswith("-")
                                or b["end_str"].startswith("-")
                            ):
                                file_has_changes = True
                                if detailed_logs_enabled:
                                    b_index = b["index"]
                                    b_start = b["start_str"]
                                    b_end = b["end_str"]
                                    log_msg = f'Subtitle block removed | Option: Remove Negative Timecodes | Index: "{b_index}" | Timecode: "{b_start} --> {b_end}"'
                                    file_subtitle_logs.append(log_msg)
                            else:
                                filtered_blocks.append(b)
                        blocks = filtered_blocks

                    # Option: Fix Misplaced Timecodes
                    if opt_fix_misplaced_timecodes:
                        blocks = fix_misplaced_timecodes(blocks, file_subtitle_logs, detailed_logs_enabled)

                    # Option: Remove Duplicate Subtitles
                    if opt_remove_duplicate_subtitles:
                        before_dup = len(blocks)
                        blocks = remove_duplicate_subtitles(blocks, file_subtitle_logs, detailed_logs_enabled)
                        if len(blocks) != before_dup:
                            file_has_changes = True

                    # Option: Fix Overlapping Timecodes
                    if opt_fix_overlapping_timecodes:
                        blocks, has_changes = fix_overlapping_timecodes(
                            blocks, file_subtitle_logs, detailed_logs_enabled
                        )
                        if has_changes:
                            file_has_changes = True

                    # Option: Remove Empty Subtitles
                    if opt_remove_empty_subtitles:
                        filtered_blocks = []
                        for b in blocks:
                            text_content = "".join(b["text_lines"]).strip()
                            if not text_content:
                                file_has_changes = True
                                if detailed_logs_enabled:
                                    b_index = b["index"]
                                    b_start = b["start_str"]
                                    b_end = b["end_str"]
                                    log_msg = f'Subtitle block removed | Option: Remove Empty Subtitles | Index: "{b_index}" | Timecode: "{b_start} --> {b_end}"'
                                    file_subtitle_logs.append(log_msg)
                            else:
                                filtered_blocks.append(b)
                        blocks = filtered_blocks

                    # Option: Add Intro Credit Subtitle
                    if opt_add_intro_credit:
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
                                    if detailed_logs_enabled:
                                        log_msg = f'Intro credit subtitle added | Timecode: "{ms_to_timecode(200)} --> {ms_to_timecode(200 + dur_ms)}"'
                                        file_subtitle_logs.append(log_msg)
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
                                        if detailed_logs_enabled:
                                            log_msg = f'Intro credit subtitle added at beginning | Timecode: "{ms_to_timecode(start_time_ms)} --> {ms_to_timecode(end_time_ms)}"'
                                            file_subtitle_logs.append(log_msg)
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
                                                if detailed_logs_enabled:
                                                    log_msg = f'Intro credit subtitle added at gap after block {k + 1} | Timecode: "{ms_to_timecode(start_time_ms)} --> {ms_to_timecode(end_time_ms)}"'
                                                    file_subtitle_logs.append(log_msg)
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
                                            if detailed_logs_enabled:
                                                log_msg = f'Intro credit subtitle added at the end | Timecode: "{ms_to_timecode(start_time_ms)} --> {ms_to_timecode(end_time_ms)}"'
                                                file_subtitle_logs.append(log_msg)

                    # Option: Reformat & Renumber Subtitles
                    if opt_reformat_renumber:
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

                        if detailed_logs_enabled:
                            log_msg = f"Reformat & Renumber completed | Total blocks renumbered: {len(blocks)}"
                            file_subtitle_logs.append(log_msg)

                # Option: Post-Process Force RTL (Remove control chars and force Right-To-Left)
                # Executed after reformat and renumber block as requested
                if opt_force_rtl:
                    rtl_processed_lines = []
                    rtl_modified_lines_count = 0

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
                        "✦",
                        "✨",
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
                        "✦",
                        "✨",
                    )

                    for index, line in enumerate(processed_lines, start=1):
                        if index_match(line) or timecode_match(line) or not line.strip():
                            rtl_processed_lines.append(line)
                        else:
                            original_text_line = line
                            clean_text = line

                            clean_text = clean_text.translate(CTRL_CHAR_TRANS)

                            # Apply RTL Trim Spaces
                            if opt_post_trim_spaces and clean_text:
                                before_post = clean_text
                                clean_text = trim_line_spaces(clean_text)
                                if before_post != clean_text:
                                    file_has_changes = True
                                    _log_change(
                                        index,
                                        "RTL Trim Spaces",
                                        before_post,
                                        clean_text,
                                        file_subtitle_logs,
                                        detailed_logs_enabled,
                                    )

                            # Apply Post-Process Option: Smart RTL Enforcement
                            if clean_text.strip():
                                line_stripped = clean_text.rstrip("\r\n")
                                line_ending = clean_text[len(line_stripped) :]

                                # Remove HTML tags AND invisible zero-width chars temporarily to check boundaries accurately
                                text_no_tags = HTML_TAG_RE.sub("", line_stripped)
                                text_no_tags = ZERO_WIDTH_RE.sub("", text_no_tags).strip()

                                if text_no_tags:
                                    # Ignore music symbols when detecting non-English content
                                    text_for_language_check = MUSIC_SYMBOLS_RE.sub("", text_no_tags).strip()

                                    # Check if the line contains any non-ASCII (non-English) characters
                                    has_non_english = bool(NON_ASCII_RE.search(text_for_language_check))

                                    if has_non_english:
                                        # Fix visually typed punctuation at the start of the line
                                        # Moves misplaced punctuation (colons, question/exclamation marks) from the start to the end
                                        if re.match(r"^((?:<[^>]+>\s*)*)([:؛!\?؟])", line_stripped):
                                            line_stripped = re.sub(
                                                r"^((?:<[^>]+>\s*)*)([:؛!\?؟])\s*(.*)$", r"\1\3\2", line_stripped
                                            )

                                        # Re-evaluate text_no_tags after modification
                                        text_no_tags = HTML_TAG_RE.sub("", line_stripped)
                                        text_no_tags = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text_no_tags).strip()

                                        # Check for music symbols before removing them to ensure they trigger RTL formatting
                                        has_music_symbol = bool(MUSIC_SYMBOLS_RE.search(text_no_tags))

                                        # Ignore music symbols for boundary checks to accurately detect punctuation
                                        text_no_tags = MUSIC_SYMBOLS_RE.sub("", text_no_tags).strip()

                                        has_symbol_start = text_no_tags.startswith(start_symbols)
                                        has_symbol_end = text_no_tags.endswith(end_symbols)

                                        # Detect if line starts with English letters or digits (to prevent forcing RTL on visually-encoded LTR lines)
                                        starts_with_english_or_digits = bool(
                                            re.match(r"^[a-zA-Z0-9\u06F0-\u06F9\u0660-\u0669]", text_no_tags)
                                        )
                                        rtl_line = line_stripped

                                        # Protect English phrases with LRM (\u200e) markers to strictly lock their internal LTR order
                                        if re.search(r"[a-zA-Z]", rtl_line):
                                            parts = re.split(r"(<[^>]+>)", rtl_line)

                                            # Regex with conditional matching to include paired punctuation (e.g. (), [], "")
                                            # If the English text is enclosed in brackets, they will be wrapped inside the LRM lock together
                                            eng_pattern = re.compile(
                                                r"(?<![a-zA-Z\d])"
                                                r"(?:(\()|(\[)|(\{)|(<)|(\")|(')|(«))?"
                                                r"([a-zA-Z\d@._\-+\'#]*[a-zA-Z][a-zA-Z\d@._\-+\'#]*(?:\s+[a-zA-Z\d@._\-+\'#]+)*)"
                                                r"(?(1)\))(?(2)\])(?(3)\})(?(4)>)(?(5)\")(?(6)')(?(7)»)"
                                                r"(?![a-zA-Z\d])"
                                            )

                                            def apply_lrm(match):
                                                # match.group(0) captures the entire valid block, including matching parentheses if present
                                                text = match.group(0)
                                                text = text.replace(" ", "\u200e \u200e")
                                                return "\u200e" + text + "\u200e"

                                            for i in range(len(parts)):
                                                if not parts[i].startswith("<"):
                                                    parts[i] = eng_pattern.sub(apply_lrm, parts[i])
                                            rtl_line = "".join(parts)

                                        # Use RLE (\u202b) and PDF (\u202c) to strictly enforce RTL direction
                                        # This forces the internal bidi algorithm to treat English words and digits as embedded inside an RTL context
                                        if (
                                            has_symbol_start
                                            or has_symbol_end
                                            or starts_with_english_or_digits
                                            or has_music_symbol
                                        ):
                                            # Place Bidi markers inside HTML tags to prevent rendering issues in players
                                            tag_pattern = r"^((?:<[^>]+>\s*)*)(.*?)(\s*(?:<[^>]+>\s*)*)$"
                                            tag_match = re.match(tag_pattern, rtl_line)
                                            if tag_match:
                                                rtl_line = (
                                                    tag_match.group(1)
                                                    + "\u202b"
                                                    + tag_match.group(2)
                                                    + "\u202c"
                                                    + tag_match.group(3)
                                                )
                                            else:
                                                rtl_line = "\u202b" + rtl_line + "\u202c"

                                        clean_text = rtl_line + line_ending
                                    else:
                                        # Skip RTL processing completely for fully English/ASCII lines
                                        clean_text = line_stripped + line_ending
                            else:
                                clean_text = line_stripped + line_ending

                            if clean_text != original_text_line:
                                file_has_changes = True
                                rtl_modified_lines_count += 1
                                _log_change(
                                    index,
                                    "Smart RTL Enforcement",
                                    original_text_line,
                                    clean_text,
                                    file_subtitle_logs,
                                    detailed_logs_enabled,
                                )

                            rtl_processed_lines.append(clean_text)

                    # Log total RTL changes once at the end if any lines were modified
                    if rtl_modified_lines_count > 0 and detailed_logs_enabled:
                        log_msg = f"Total subtitle lines RTL formatted: {rtl_modified_lines_count}"
                        file_subtitle_logs.append(log_msg)

                    processed_lines = rtl_processed_lines

                # Construct output file path structure
                name_part, _ = os.path.splitext(filename)

                # Enforce SRT format for the output file, regardless of the input extension
                output_filename = f"{name_part}_Edited.srt"
                output_file_path = os.path.join(output_dir, output_filename)

                # Use explicit UTF-8 if setting is enabled, otherwise use original detected encoding
                out_encoding = "utf-8-sig" if opt_encode_utf8 else file_encoding

                with open(output_file_path, "w", encoding=out_encoding) as f:
                    f.writelines(processed_lines)

                file_process_logs.append(f"Processed and saved successfully: {output_filename}")
                if detailed_logs_enabled:
                    file_subtitle_logs.append(f"Finished tracking. Total changes occurred: {file_has_changes}")

                # Post processing clean up option: Delete Original
                if opt_delete_original:
                    os.remove(file_path)
                    file_process_logs.append(f"Original file deleted by request: {filename}")

                # Increment successful tracking counter
                with self._counter_lock:
                    self.successful_count += 1
                self._report_progress()

            except Exception as e:
                file_process_logs.append(f"Failed to process file {filename} due to: {str(e)}")
                self._report_progress()
                # Increment failed tracking counter
                with self._counter_lock:
                    self.failed_count += 1

            finally:
                if local_lines_processed:
                    with self._counter_lock:
                        self.total_lines_processed += local_lines_processed
                        reported_lines = self.total_lines_processed
                    local_lines_processed = 0
                    self._report_progress()
                    self._report_worker_line_progress(reported_lines)
                elif self._worker_mode:
                    self._report_worker_line_progress(self.total_lines_processed)

                if opt_delete_converted_temp_files and converted_temp_file and os.path.isfile(actual_file_path):
                    try:
                        os.remove(actual_file_path)
                        file_process_logs.append(
                            f"Temporary converted SRT file deleted by request: {os.path.basename(actual_file_path)}"
                        )
                    except Exception as e:
                        file_process_logs.append(
                            f"Failed to delete temporary converted SRT file {os.path.basename(actual_file_path)}: {str(e)}"
                        )

                # Flush timestamped process logs while preserving the timestamp captured at append time
                if file_process_logs and current_file_dir and os.path.isdir(current_file_dir):
                    process_log_dir = os.path.join(current_file_dir, "Logs")
                    os.makedirs(process_log_dir, exist_ok=True)
                    process_log_file = os.path.join(process_log_dir, "process-logs.txt")

                    if self._worker_mode:
                        self._deferred_process_logs.append((process_log_file, list(file_process_logs)))
                    else:
                        try:
                            with self._log_lock:
                                with open(process_log_file, "a", encoding="utf-8") as f:
                                    f.writelines(
                                        f"[{timestamp}] {message}\n" for timestamp, message in file_process_logs
                                    )
                        except Exception as e:
                            print(f"Process logging failed: {e}")

                # Flush timestamped subtitle logs while preserving the timestamp captured at append time
                if (
                    file_subtitle_logs
                    and detailed_logs_enabled
                    and current_file_dir
                    and os.path.isdir(current_file_dir)
                ):
                    subtitle_log_dir = os.path.join(current_file_dir, "Logs", "Subtitle-Logs")
                    os.makedirs(subtitle_log_dir, exist_ok=True)
                    subtitle_log_file = os.path.join(subtitle_log_dir, f"{filename}_changelogs.txt")

                    try:
                        with self._log_lock:
                            with open(subtitle_log_file, "a", encoding="utf-8") as f:
                                for timestamp, message in file_subtitle_logs:
                                    f.write(f"[{timestamp}] {message}\n")
                    except Exception as e:
                        print(f"Subtitle detailed logging failed: {e}")

        if self._worker_mode:
            for worker_file_path in srt_files_paths:
                _process_file(worker_file_path)

        elif use_parallel:
            total_input_lines = 0
            for file_path in srt_files_paths:
                total_input_lines += self._count_file_lines(file_path)
            self.total_input_lines = total_input_lines

            manager = multiprocessing.Manager()
            progress_queue = manager.Queue()
            file_progress = {file_path: 0 for file_path in srt_files_paths}

            try:
                with ProcessPoolExecutor(
                    max_workers=max_workers,
                    initializer=_init_process_worker,
                    initargs=(self.options, progress_queue),
                ) as executor:
                    future_to_path = {
                        executor.submit(_process_file_in_worker, file_path): file_path for file_path in srt_files_paths
                    }

                    pending = set(future_to_path)
                    while pending:
                        while True:
                            try:
                                progress_file, processed_lines = progress_queue.get_nowait()
                            except Exception:
                                break

                            if progress_file in file_progress:
                                file_progress[progress_file] = max(file_progress[progress_file], processed_lines)

                            if self.total_input_lines > 0:
                                actual_processed = sum(file_progress.values())
                                self.total_lines_processed = max(self.total_lines_processed, actual_processed)
                                self._report_progress()

                        done, pending = wait(pending, timeout=0.05, return_when=FIRST_COMPLETED)

                        for future in done:
                            file_path = future_to_path[future]

                            try:
                                result = future.result() or {}
                                self.successful_count += result.get("successful_count", 0)
                                self.failed_count += result.get("failed_count", 0)
                                file_progress[file_path] = max(
                                    file_progress.get(file_path, 0),
                                    result.get("total_lines_processed", 0),
                                )
                                self.total_lines_processed = sum(file_progress.values())
                                self._report_progress()

                                for process_log_file, entries in result.get("process_logs", []):
                                    if not entries:
                                        continue
                                    try:
                                        os.makedirs(os.path.dirname(process_log_file), exist_ok=True)
                                        with open(process_log_file, "a", encoding="utf-8") as f:
                                            f.writelines(f"[{timestamp}] {message}\n" for timestamp, message in entries)
                                    except Exception as e:
                                        print(f"Process logging failed: {e}")
                            except Exception as e:
                                self.failed_count += 1
                                print(f"Parallel worker failed for {os.path.basename(file_path)}: {e}")

                    while True:
                        try:
                            progress_file, processed_lines = progress_queue.get_nowait()
                        except Exception:
                            break

                        if progress_file in file_progress:
                            file_progress[progress_file] = max(file_progress[progress_file], processed_lines)

                if self.total_input_lines > 0:
                    self.total_lines_processed = self.total_input_lines
                    self._report_progress()
            finally:
                try:
                    progress_queue.close()
                except Exception:
                    pass
                try:
                    manager.shutdown()
                except Exception:
                    pass

        else:
            _process_file_serial = _process_file
            for file_path in srt_files_paths:
                _process_file_serial(file_path)

            if self.total_input_lines > 0:
                self.total_lines_processed = self.total_input_lines

            self._report_progress()

        self._report_complete()
        self.elapsed_time = time.time() - start_time

        if not self._worker_mode:
            if self.target_files:
                Logger.log_process(
                    "All single file tasks completed inside process pipeline.",
                    os.path.dirname(self.target_files[0]) if self.target_files else "",
                )
            else:
                Logger.log_process("All tasks completed inside process pipeline.", self.folder_path)

        if self._worker_mode:
            return {
                "successful_count": self.successful_count,
                "failed_count": self.failed_count,
                "total_lines_processed": self.total_lines_processed,
                "process_logs": self._deferred_process_logs,
            }
