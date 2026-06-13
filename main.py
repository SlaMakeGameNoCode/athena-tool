"""Athena Launcher - Entry point cho exe.
Không chứa logic app, chỉ load từ root folder."""

import sys
import os

APP_VERSION = "1.0.0"

if getattr(sys, 'frozen', False):
    RUNNING_DIR = os.path.dirname(sys.executable)
    os.chdir(RUNNING_DIR)
else:
    RUNNING_DIR = os.path.dirname(os.path.abspath(__file__))

# Add RUNNING_DIR to the top of sys.path so that disk versions of modules are imported first
sys.path.insert(0, RUNNING_DIR)

# Handle the submitter and preview_helper subprocess calls if they were invoked via PyInstaller exe
if len(sys.argv) > 1:
    if sys.argv[1] == "submitter.py":
        import submitter
        submitter.main()
        sys.exit(0)
    elif sys.argv[1] == "preview_helper.py":
        import preview_helper
        preview_helper.main()
        sys.exit(0)

# Import và chạy app chính
import app_core
if __name__ == "__main__":
    app_core.run(RUNNING_DIR, APP_VERSION)
