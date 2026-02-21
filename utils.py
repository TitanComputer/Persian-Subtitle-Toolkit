from app_info import *
import time
import threading


# --- Single Instance Logic START with Timeout ---
class AppLock:
    def __init__(self, app_name, timeout=60):
        self.app_name = app_name
        self.timeout = timeout
        self.lock_dir = os.path.join(os.getenv("LOCALAPPDATA", os.getenv("HOME", "/tmp")), app_name)
        self.lock_file = os.path.join(self.lock_dir, "app.lock")
        self.active = False
        os.makedirs(self.lock_dir, exist_ok=True)

    def acquire(self):
        if os.path.exists(self.lock_file):
            age = time.time() - os.path.getmtime(self.lock_file)
            if age > self.timeout:
                os.remove(self.lock_file)
            else:
                return False

        try:
            with open(self.lock_file, "w") as f:
                f.write(str(os.getpid()))
            self.active = True
            return True
        except:
            return False

    def start_updater(self):
        if self.active:
            thread = threading.Thread(target=self._update_loop, daemon=True)
            thread.start()

    def _update_loop(self):
        while self.active:
            try:
                os.utime(self.lock_file, None)
            except:
                break
            time.sleep(self.timeout / 2)

    def release(self):
        self.active = False
        if os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
            except:
                pass


# --- Single Instance Logic END with Timeout ---
