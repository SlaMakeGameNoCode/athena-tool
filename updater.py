"""
Updater module — Kiểm tra và tải bản cập nhật từ GitHub.
Không cần cài Git trên máy user. Dùng GitHub REST API + ZIP download.
"""

import os
import json
import shutil
import zipfile
import tempfile
import requests

# ============================================================
# CẤU HÌNH GITHUB REPO
# ============================================================
GITHUB_REPO = "SlaMakeGameNoCode/athena-tool"
GITHUB_BRANCH = "main"

VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/version.json"
ZIP_URL = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"

# Các file/thư mục SẼ ĐƯỢC CẬP NHẬT từ GitHub
UPDATE_INCLUDES = [
    "main.py",
    "app_core.py",
    "submitter.py",
    "ai_processor.py",
    "sync_rocket.py",
    "sync_git.py",
    "sync_email.py",
    "workai_api.py",
    "sync_calendar.py",
    "sync_gitlab.py",
    "updater.py",
    "version.json",
    "requirements.txt",
    "static",
]

# Các file/thư mục KHÔNG BAO GIỜ ghi đè (dữ liệu riêng của user)
UPDATE_EXCLUDES = [
    ".env",
    "config.json",
    "projects.json",
    "chat_raw.json",
    "git_raw.json",
    "saved_raw_tasks.json",
    "memorytask.md",
    "tasks.json",
    "submitted.json",
    "submission_status.json",
    "last_sync.txt",
    "saved_kpi_tasks.json",
    "exe_updated.json",
]


def check_missing_files(base_dir):
    """Quét danh sách UPDATE_INCLUDES và trả về các file/folder bị thiếu."""
    missing = []
    for item in UPDATE_INCLUDES:
        path = os.path.join(base_dir, item)
        if not os.path.exists(path):
            missing.append(item)
    return {
        "has_missing": len(missing) > 0,
        "missing_files": missing,
        "total_expected": len(UPDATE_INCLUDES),
        "total_found": len(UPDATE_INCLUDES) - len(missing)
    }



def get_local_version(base_dir):
    """Đọc phiên bản hiện tại từ version.json local."""
    version_file = os.path.join(base_dir, "version.json")
    if not os.path.exists(version_file):
        import sys
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            version_file = os.path.join(sys._MEIPASS, "version.json")
            
    if os.path.exists(version_file):
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("version", "0.0.0")
        except Exception:
            pass
    return "0.0.0"


def check_update(current_version):
    """Kiểm tra phiên bản mới trên GitHub.
    
    Returns:
        dict: {has_update, current_version, remote_version, changelog, released_at}
    """
    try:
        import time
        url = f"{VERSION_URL}?t={int(time.time())}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        remote = resp.json()
        remote_ver = remote.get("version", "0.0.0")
        has_update = _compare_versions(remote_ver, current_version) > 0
        return {
            "has_update": has_update,
            "current_version": current_version,
            "remote_version": remote_ver,
            "changelog": remote.get("changelog", ""),
            "released_at": remote.get("released_at", ""),
            "exe_update": remote.get("exe_update", ""),
        }
    except requests.exceptions.ConnectionError:
        return {
            "has_update": False,
            "current_version": current_version,
            "error": "Không có kết nối mạng.",
            "exe_update": "",
        }
    except Exception as e:
        return {
            "has_update": False,
            "current_version": current_version,
            "error": str(e),
            "exe_update": "",
        }


def check_exe_update(base_dir):
    marker_file = os.path.join(base_dir, "exe_updated.json")
    applied_ver = ""
    if os.path.exists(marker_file):
        try:
            with open(marker_file, "r", encoding="utf-8") as f:
                applied_ver = json.load(f).get("version", "")
        except Exception:
            pass

    current = get_local_version(base_dir) or "0.0.0"
    info = check_update(current)
    exe_url = info.get("exe_update", "")
    remote_ver = info.get("remote_version", "")

    if exe_url and remote_ver and remote_ver != applied_ver:
        return True, exe_url, remote_ver
    return False, "", ""


def apply_update(base_dir):
    """Tải ZIP source từ GitHub và cập nhật các file source code.
    
    Quy trình:
    1. Download ZIP từ GitHub
    2. Giải nén vào thư mục tạm
    3. Copy các file source code (theo UPDATE_INCLUDES) vào base_dir
    4. Bỏ qua các file dữ liệu user (theo UPDATE_EXCLUDES)
    5. Dọn dẹp
    
    Returns:
        dict: {success, message, version}
    """
    tmp_dir = None
    zip_path = None
    
    try:
        # 1. Download ZIP
        print("[Updater] Đang tải bản cập nhật từ GitHub...")
        resp = requests.get(ZIP_URL, timeout=120, stream=True)
        resp.raise_for_status()
        
        # Save to temp file
        tmp_dir = tempfile.mkdtemp(prefix="athena_update_")
        zip_path = os.path.join(tmp_dir, "update.zip")
        
        total_size = 0
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                total_size += len(chunk)
        
        print(f"[Updater] Đã tải {total_size / 1024:.1f} KB")
        
        # 2. Giải nén
        print("[Updater] Đang giải nén...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)
        
        # GitHub ZIP tạo folder dạng "athena-tool-main/"
        extracted_dirs = [d for d in os.listdir(tmp_dir) 
                         if os.path.isdir(os.path.join(tmp_dir, d))]
        if not extracted_dirs:
            raise Exception("Không tìm thấy thư mục trong file ZIP.")
        
        extracted_root = os.path.join(tmp_dir, extracted_dirs[0])
        
        # 3. Copy các file/thư mục được phép cập nhật
        updated_files = []
        for item_name in os.listdir(extracted_root):
            src_path = os.path.join(extracted_root, item_name)
            dst_path = os.path.join(base_dir, item_name)
            
            # Bỏ qua file dữ liệu user
            if item_name in UPDATE_EXCLUDES:
                continue
            
            # Chỉ copy file trong danh sách cho phép
            if item_name in UPDATE_INCLUDES:
                if os.path.isdir(src_path):
                    # Copy thư mục (e.g. static/)
                    if os.path.exists(dst_path):
                        shutil.rmtree(dst_path)
                    shutil.copytree(src_path, dst_path)
                    updated_files.append(f"{item_name}/")
                else:
                    # Copy file
                    shutil.copy2(src_path, dst_path)
                    updated_files.append(item_name)
        
        # 4. Đọc version mới
        new_version = get_local_version(base_dir)
        
        print(f"[Updater] Cập nhật thành công! v{new_version}")
        print(f"[Updater] Đã cập nhật: {', '.join(updated_files)}")
        
        return {
            "success": True,
            "message": f"Đã cập nhật lên phiên bản {new_version}",
            "version": new_version,
            "updated_files": updated_files,
        }
        
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "message": "Không có kết nối mạng. Vui lòng kiểm tra lại.",
        }
    except Exception as e:
        print(f"[Updater] Lỗi: {e}")
        return {
            "success": False,
            "message": f"Lỗi khi cập nhật: {str(e)}",
        }
    finally:
        # Dọn dẹp
        if tmp_dir and os.path.exists(tmp_dir):
            try:
                shutil.rmtree(tmp_dir)
            except Exception:
                pass


def apply_exe_update(base_dir, exe_update_url):
    tmp_dir = None
    try:
        import subprocess
        tmp_dir = tempfile.mkdtemp(prefix="athena_exe_")
        zip_path = os.path.join(tmp_dir, "update.zip")

        print("[Updater] Đang tải bản cập nhật EXE...")
        resp = requests.get(exe_update_url, timeout=300, stream=True)
        resp.raise_for_status()

        total_size = 0
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                total_size += len(chunk)
        print(f"[Updater] Đã tải {total_size / 1024:.1f} KB")

        print("[Updater] Đang giải nén...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp_dir)

        extracted_items = [d for d in os.listdir(tmp_dir) if os.path.isdir(os.path.join(tmp_dir, d)) and d != os.path.basename(zip_path).replace(".zip", "")]
        if not extracted_items:
            extracted_items = [d for d in os.listdir(tmp_dir) if os.path.isdir(os.path.join(tmp_dir, d))]
        if extracted_items:
            src_dir = os.path.join(tmp_dir, extracted_items[0])
        else:
            src_dir = tmp_dir

        bat_path = os.path.join(tempfile.gettempdir(), "_athena_exe_update.bat")
        with open(bat_path, "w", encoding="ascii") as bf:
            bf.write("@echo off\r\n")
            bf.write("ping 127.0.0.1 -n 3 > nul\r\n")
            bf.write(f'xcopy /E /Y /H /R "{src_dir}\\*" "{base_dir}\\"\r\n')
            bf.write(f'cd /d "{base_dir}"\r\n')
            bf.write(f'start "" "Athena.exe"\r\n')
            bf.write(f'rmdir /S /Q "{tmp_dir}"\r\n')
            bf.write(f'del "%~f0"\r\n')

        CREATE_NEW_PROCESS_GROUP = 0x00000200
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(
            f'cmd.exe /c "{bat_path}"',
            shell=True,
            creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
            close_fds=True,
        )
        return {"success": True, "message": "Đang cập nhật EXE, ứng dụng sẽ tự khởi động lại..."}

    except Exception as e:
        print(f"[Updater] Lỗi cập nhật EXE: {e}")
        if tmp_dir and os.path.exists(tmp_dir):
            try:
                shutil.rmtree(tmp_dir)
            except Exception:
                pass
        return {"success": False, "message": f"Lỗi cập nhật EXE: {str(e)}"}


def _compare_versions(v1, v2):
    """So sánh 2 version string (semver đơn giản).
    Returns: >0 nếu v1 > v2, 0 nếu bằng, <0 nếu v1 < v2
    """
    def parse(v):
        try:
            return [int(x) for x in v.split(".")]
        except (ValueError, AttributeError):
            return [0]
    
    parts1 = parse(v1)
    parts2 = parse(v2)
    
    # Pad to same length
    max_len = max(len(parts1), len(parts2))
    parts1.extend([0] * (max_len - len(parts1)))
    parts2.extend([0] * (max_len - len(parts2)))
    
    for a, b in zip(parts1, parts2):
        if a != b:
            return a - b
    return 0
