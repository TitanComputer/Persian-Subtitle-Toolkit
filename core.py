from utils import *


class SubtitleProcessor:
    def __init__(self, folder_path, options=None):
        self.folder_path = folder_path
        self.options = options if options else {}

    def run(self):
        if not self.folder_path or not os.path.isdir(self.folder_path):
            return

        # Define output directory path
        output_dir = os.path.join(self.folder_path, "Outputs")
        os.makedirs(output_dir, exist_ok=True)

        # Get list of all srt files in target directory
        all_files = os.listdir(self.folder_path)
        srt_files = [f for f in all_files if f.lower().endswith(".srt")]

        if not srt_files:
            Logger.log_process("No subtitle files (.srt) found to process.", self.folder_path)
            return

        Logger.log_process(f"Process started. Found {len(srt_files)} file(s).", self.folder_path)

        for filename in srt_files:
            file_path = os.path.join(self.folder_path, filename)
            Logger.log_process(f"Identified file: {filename}", self.folder_path)

            try:
                # Read original file contents content safely
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                processed_lines = []
                file_has_changes = False

                if self.options.get("detailed_subtitle_logs", 1):
                    Logger.log_subtitle_change(self.folder_path, filename, f"Started tracking changes for: {filename}")

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

                    # Check if line was modified to log details
                    if current_line != original_line:
                        file_has_changes = True
                        if self.options.get("detailed_subtitle_logs", 1):
                            log_msg = f"Line {index} modified | Option: Trim Spaces | Before: '{original_line.rstrip("\n")}' -> After: '{current_line.rstrip("\n")}'"
                            Logger.log_subtitle_change(self.folder_path, filename, log_msg)

                    processed_lines.append(current_line)

                # Construct output file path structure
                name_part, ext_part = os.path.splitext(filename)
                output_filename = f"{name_part}_Edited{ext_part}"
                output_file_path = os.path.join(output_dir, output_filename)

                with open(output_file_path, "w", encoding="utf-8") as f:
                    f.writelines(processed_lines)

                Logger.log_process(f"Processed and saved successfully: {output_filename}", self.folder_path)
                if self.options.get("detailed_subtitle_logs", 1):
                    Logger.log_subtitle_change(
                        self.folder_path, filename, f"Finished tracking. Total changes occurred: {file_has_changes}"
                    )

                # Post processing clean up option: Delete Original
                if self.options.get("delete_original", 0):
                    os.remove(file_path)
                    Logger.log_process(f"Original file deleted by request: {filename}", self.folder_path)

            except Exception as e:
                Logger.log_process(f"Failed to process file {filename} due to: {str(e)}", self.folder_path)

        Logger.log_process("All tasks completed inside process pipeline.", self.folder_path)
