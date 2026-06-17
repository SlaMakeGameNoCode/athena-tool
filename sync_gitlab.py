import os
import json
import requests
import datetime

def load_config():
    config_file = "config.json"
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def main(last_sync_ms=None, output_path=None):
    print("Bắt đầu đồng bộ GitLab commits + diff files via REST API...")
    config = load_config()
    
    gitlab_servers = []
    if "gitlab_servers" in config:
        gitlab_servers = config.get("gitlab_servers", [])
    else:
        comp_creds_path = os.path.join("CompanySkills", "credentials.json")
        if os.path.exists(comp_creds_path):
            try:
                with open(comp_creds_path, "r", encoding="utf-8") as f:
                    creds = json.load(f)
                    gitlab_servers = creds.get("gitlab-servers", [])
            except Exception:
                pass
                
    if not gitlab_servers:
        print("[GitLab Sync] Không tìm thấy cấu hình gitlab-servers.")
        return
        
    since_date = (datetime.date.today() - datetime.timedelta(days=1)).isoformat() + "T00:00:00Z"
    all_gitlab_commits = []
    
    for server in gitlab_servers:
        name = server.get("name")
        url = server.get("url", "").rstrip("/")
        token = server.get("token")
        repos = server.get("repositories", [])
        
        if not url or not token:
            continue
            
        headers = {"PRIVATE-TOKEN": token}
        
        user_email = ""
        try:
            user_res = requests.get(f"{url}/api/v4/user", headers=headers, timeout=10)
            if user_res.status_code == 200:
                user_data = user_res.json()
                user_email = user_data.get("email", "")
        except Exception as e:
            print(f"[GitLab Sync] Lỗi kết nối {name}: {e}")
            continue
            
        for repo in repos:
            project_key = repo.get("project-key")
            path_with_namespace = repo.get("path_with_namespace")
            branches = repo.get("branches", ["main", "master", "develop", "Develop"])
            
            if not path_with_namespace:
                continue
                
            import urllib.parse
            encoded_path = urllib.parse.quote_plus(path_with_namespace)
            
            project_commits = []
            for branch in branches:
                commits_url = f"{url}/api/v4/projects/{encoded_path}/repository/commits"
                params = {
                    "ref_name": branch,
                    "since": since_date,
                    "per_page": 50
                }
                try:
                    res = requests.get(commits_url, headers=headers, params=params, timeout=10)
                    if res.status_code == 200:
                        commits = res.json()
                        for c in commits:
                            author_email = c.get("author_email", "")
                            if user_email and author_email != user_email:
                                continue
                            
                            title = c.get("title") or ""
                            message = c.get("message") or ""
                            sha = c.get("id") or ""
                            if title.startswith("Merge branch") or "Merge" in title:
                                continue
                                
                            # Lấy danh sách file thay đổi (diff) của commit này
                            changed_files = []
                            if sha:
                                diff_url = f"{url}/api/v4/projects/{encoded_path}/repository/commits/{sha}/diff"
                                try:
                                    diff_res = requests.get(diff_url, headers=headers, timeout=10)
                                    if diff_res.status_code == 200:
                                        diff_items = diff_res.json()
                                        for diff in diff_items:
                                            # Ưu tiên new_path (đường dẫn mới)
                                            filepath = diff.get("new_path") or diff.get("old_path")
                                            if filepath:
                                                filename = os.path.basename(filepath)
                                                changed_files.append(filename)
                                except Exception as diff_err:
                                    print(f"      [!] Lỗi lấy diff cho commit {sha[:8]}: {diff_err}")
                                    
                            files_str = ""
                            if changed_files:
                                # Chỉ lấy tối đa 10 files để tránh làm tràn token của LLM
                                files_str = f" | Files changed: {', '.join(changed_files[:10])}"
                                if len(changed_files) > 10:
                                    files_str += f" (và {len(changed_files) - 10} file khác)"
                                    
                            project_commits.append({
                                "sender": c.get("author_name", "GitLab"),
                                "text": f"Commit: {message.strip()}{files_str}",
                                "date": c.get("committed_date")
                            })
                except Exception as e:
                    print(f"[GitLab Sync] Lỗi lấy commits cho {path_with_namespace}: {e}")
                    
            if project_commits:
                all_gitlab_commits.append({
                    "room_name": f"GitLab - {path_with_namespace} ({project_key})",
                    "messages": project_commits
                })

    if output_path:
        if all_gitlab_commits:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(all_gitlab_commits, f, ensure_ascii=False, separators=(",", ":"))
            print(f"[GitLab Sync] Đã đồng bộ thành công {len(all_gitlab_commits)} repository GitLab.")
        return

    chat_raw_path = "chat_raw.json"
    existing_chat = []
    if os.path.exists(chat_raw_path):
        try:
            with open(chat_raw_path, "r", encoding="utf-8") as f:
                existing_chat = json.load(f)
        except Exception:
            pass
            
    if all_gitlab_commits:
        existing_chat.extend(all_gitlab_commits)
        try:
            with open(chat_raw_path, "w", encoding="utf-8") as f:
                json.dump(existing_chat, f, ensure_ascii=False, separators=(",", ":"))
            print(f"[GitLab Sync] Đã đồng bộ thành công {len(all_gitlab_commits)} repository GitLab.")
        except Exception as e:
            print(f"[GitLab Sync] Lỗi lưu chat_raw.json: {e}")

if __name__ == "__main__":
    main()
