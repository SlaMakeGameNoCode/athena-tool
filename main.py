import sys
import os
import datetime

# Log startup immediately
try:
    log_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(log_dir, "Athena_startup.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.datetime.now()}] --- Athena.exe STARTED ---\n")
        f.write(f"[{datetime.datetime.now()}] sys.executable: {sys.executable}\n")
        f.write(f"[{datetime.datetime.now()}] sys.argv: {sys.argv}\n")
        f.write(f"[{datetime.datetime.now()}] working dir: {os.getcwd()}\n")
except Exception:
    pass

APP_VERSION = "1.0.38"

import json

if getattr(sys, 'frozen', False):
    RUNNING_DIR = os.path.dirname(sys.executable)
    os.chdir(RUNNING_DIR)
else:
    RUNNING_DIR = os.path.dirname(os.path.abspath(__file__))

APP_VERSION = "1.1.0"
version_path = os.path.join(RUNNING_DIR, "version.json")
if not os.path.exists(version_path):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        version_path = os.path.join(sys._MEIPASS, "version.json")
if os.path.exists(version_path):
    try:
        with open(version_path, "r", encoding="utf-8") as f:
            APP_VERSION = json.load(f).get("version", APP_VERSION)
            try:
                with open(log_path, "a", encoding="utf-8") as f_log:
                    f_log.write(f"[{datetime.datetime.now()}] Loaded version from version.json: {APP_VERSION}\n")
            except Exception:
                pass
    except Exception as e:
        try:
            with open(log_path, "a", encoding="utf-8") as f_log:
                f_log.write(f"[{datetime.datetime.now()}] Error reading version.json: {str(e)}\n")
        except Exception:
            pass

# Add RUNNING_DIR to the top of sys.path so that disk versions of modules are imported first
sys.path.insert(0, RUNNING_DIR)

# Handle the submitter and preview_helper subprocess calls if they were invoked via PyInstaller exe
if len(sys.argv) > 1:
    first_arg = os.path.basename(sys.argv[1]).lower()
    if first_arg == "submitter.py":
        import submitter
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        submitter.main()
        sys.exit(0)
    elif first_arg == "preview_helper.py":
        import preview_helper
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        preview_helper.main()
        sys.exit(0)

# Import và chạy app chính
try:
    with open(log_path, "a", encoding="utf-8") as f_log:
        f_log.write(f"[{datetime.datetime.now()}] Importing app_core...\n")
except Exception:
    pass

import app_core

try:
    with open(log_path, "a", encoding="utf-8") as f_log:
        f_log.write(f"[{datetime.datetime.now()}] Running app_core.run...\n")
except Exception:
    pass

if __name__ == "__main__":
    app_core.run(RUNNING_DIR, APP_VERSION)
