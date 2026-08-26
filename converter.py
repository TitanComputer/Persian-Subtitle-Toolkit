from rules import *
from utils import *


def convert_txt_to_srt(file_path, output_path, process_logs, subtitle_logs, detailed_logs_enabled):
    """
    Validates and converts a TXT subtitle file to SRT format.
    The TXT file must already follow the standard SRT block structure.
    """
    try:
        # Use utf-8-sig to automatically handle BOM and prevent validation failure
        with open(file_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except UnicodeDecodeError:
        return False

    # Validation: Check if the file contains standard SRT timecodes
    if re.search(r"\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}", content):
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        process_logs.append(f"Format Conversion | Validated TXT and saved as SRT: {os.path.basename(output_path)}")
        if detailed_logs_enabled:
            subtitle_logs.append("Option: Format Conversion | Converted from TXT to SRT format.")
        return True

    return False


def convert_vtt_to_srt(file_path, output_path, process_logs, subtitle_logs, detailed_logs_enabled):
    """
    Validates and converts a VTT subtitle file to SRT format.
    Removes the WEBVTT header, fixes timecode formatting, adds block indices, and cleans HTML/VTT tags.
    """
    try:
        # Use utf-8-sig to automatically handle BOM and prevent WEBVTT check failure
        with open(file_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except UnicodeDecodeError:
        return False

    # Strip spaces and manually remove any lingering BOM just in case
    if not content.strip().lstrip("\ufeff").startswith("WEBVTT"):
        return False

    blocks = content.split("\n\n")
    srt_lines = []
    index = 1

    # Regex for VTT timecode, accommodating optional hours (e.g., 00:00.000 or 00:00:00.000)
    timecode_pattern = re.compile(
        r"(?:(\d{2,}):)?(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(?:(\d{2,}):)?(\d{2}):(\d{2})\.(\d{3})"
    )

    for block in blocks:
        lines = block.strip().split("\n")
        if not lines:
            continue

        timecode_line_idx = -1
        for i, line in enumerate(lines):
            if "-->" in line:
                timecode_line_idx = i
                break

        if timecode_line_idx == -1:
            continue

        timecode_line = lines[timecode_line_idx]
        match = timecode_pattern.search(timecode_line)
        if not match:
            continue

        def format_time(h, m, s, ms):
            h = h if h else "00"
            return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(ms):03d}"

        start_time = format_time(match.group(1), match.group(2), match.group(3), match.group(4))
        end_time = format_time(match.group(5), match.group(6), match.group(7), match.group(8))

        srt_timecode = f"{start_time} --> {end_time}"
        text_lines = lines[timecode_line_idx + 1 :]

        # Clean VTT specific tags (e.g., <c.colorff9800>)
        clean_text_lines = []
        for t_line in text_lines:
            t_line = re.sub(r"<[^>]+>", "", t_line)
            clean_text_lines.append(t_line)

        text_content = "\n".join(clean_text_lines).strip()
        if not text_content:
            continue

        srt_lines.append(f"{index}\n{srt_timecode}\n{text_content}\n\n")
        index += 1

    if not srt_lines:
        return False

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(srt_lines)

    process_logs.append(f"Format Conversion | Validated VTT and converted to SRT: {os.path.basename(output_path)}")
    if detailed_logs_enabled:
        subtitle_logs.append("Option: Format Conversion | Converted from VTT to SRT format.")

    return True


def convert_ass_to_srt(
    file_path, output_path, process_logs, subtitle_logs, detailed_logs_enabled, include_comments=False
):
    """
    Validates and converts an ASS subtitle file to SRT format.
    Extracts Dialogue and Comment lines, reformats timecodes, removes style brackets {}, handles duplicate skip,
    and merges Note-style lines that share the exact same timestamp with their preceding dialogue line.
    """
    try:
        # Use utf-8-sig to automatically handle BOM
        with open(file_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        return False

    events_started = False
    srt_entries = []
    prev_timecode = None

    def format_ass_time(ass_time):
        try:
            h, m, s_cs = ass_time.split(":")
            s, cs = s_cs.split(".")
            # ASS centiseconds (cs) need to be multiplied by 10 to get milliseconds
            return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(cs)*10:03d}"
        except ValueError:
            return "00:00:00,000"

    for line in lines:
        line = line.strip()
        if line == "[Events]":
            events_started = True
            continue

        if events_started and (line.startswith("Dialogue:") or (include_comments and line.startswith("Comment:"))):
            parts = line.split(":", 1)
            if len(parts) < 2:
                continue

            event_data = parts[1].strip().split(",", 9)
            if len(event_data) < 10:
                continue

            start_ass = event_data[1].strip()
            end_ass = event_data[2].strip()
            style_ass = event_data[3].strip()
            text_ass = event_data[9].strip()

            start_srt = format_ass_time(start_ass)
            end_srt = format_ass_time(end_ass)
            timecode = f"{start_srt} --> {end_srt}"

            # Remove ASS style override tags enclosed in {}
            text_clean = re.sub(r"\{.*?\}", "", text_ass)

            # Replace literal \N or \n with actual newlines
            text_clean = text_clean.replace(r"\N", "\n").replace(r"\n", "\n").strip()

            if not text_clean:
                continue

            # Merge Note lines sharing the exact same timecode with the preceding line
            is_note = "note" in style_ass.lower()
            if timecode == prev_timecode and srt_entries:
                prev_entry = srt_entries[-1]
                if is_note or "note" in prev_entry.get("style", "").lower():
                    prev_entry["text"] += f"\n{text_clean}"
                    continue
                # Skip normal duplicate timecodes based on the previous line
                continue

            prev_timecode = timecode
            srt_entries.append({"timecode": timecode, "text": text_clean, "style": style_ass})

    if not srt_entries:
        return False

    srt_lines = []
    for index, entry in enumerate(srt_entries, start=1):
        srt_lines.append(f"{index}\n{entry['timecode']}\n{entry['text']}\n\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(srt_lines)

    process_logs.append(f"Format Conversion | Validated ASS and converted to SRT: {os.path.basename(output_path)}")
    if detailed_logs_enabled:
        subtitle_logs.append("Option: Format Conversion | Converted from ASS to SRT format.")

    return True


def process_and_convert_if_needed(
    file_path, process_logs, subtitle_logs, detailed_logs_enabled, include_ass_comments=False
):
    """
    Checks the file extension. If it is an alternative supported format (TXT, VTT, ASS),
    validates and converts it to SRT before standard processing begins.
    Returns the file path (new SRT if converted, or original) and a boolean indicating validation success.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".srt":
        return file_path, True

    dir_name = os.path.dirname(file_path)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(dir_name, base_name + ".srt")

    success = False
    if ext == ".txt":
        success = convert_txt_to_srt(file_path, output_path, process_logs, subtitle_logs, detailed_logs_enabled)
    elif ext == ".vtt":
        success = convert_vtt_to_srt(file_path, output_path, process_logs, subtitle_logs, detailed_logs_enabled)
    elif ext == ".ass":
        success = convert_ass_to_srt(
            file_path, output_path, process_logs, subtitle_logs, detailed_logs_enabled, include_ass_comments
        )

    if success:
        return output_path, True

    return file_path, False
