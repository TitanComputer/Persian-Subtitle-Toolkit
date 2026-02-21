from utils import *


class SubtitleProcessor:
    def __init__(self, folder_path):
        self.folder_path = folder_path

    def run(self):
        if not self.folder_path or not os.path.isdir(self.folder_path):
            return
        pass
