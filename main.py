"""Athena Launcher - Entry point cho exe.
Không chứa logic app, chỉ load từ root folder."""

import sys
import os

APP_VERSION = "1.0.32"

import json

if getattr(sys, 'frozen', False):
    RUNNING_DIR = os.path.dirname(sys.executable)
    os.chdir(RUNNING_DIR)
else:
    RUNNING_DIR = os.path.dirname(os.path.abspath(__file__))

APP_VERSION = "1.0.32"
version_path = os.path.join(RUNNING_DIR, "version.json")
if os.path.exists(version_path):
    try:
        with open(version_path, "r", encoding="utf-8") as f:
            APP_VERSION = json.load(f).get("version", APP_VERSION)
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
import app_core
if __name__ == "__main__":
    app_core.run(RUNNING_DIR, APP_VERSION)
