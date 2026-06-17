import os
import json
import requests

class WorkAIAPI:
    def __init__(self, base_url="https://workai-be.horus.io.vn/api"):
        self.base_url = base_url
        self.token = None
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        self.user_info = None

    def login(self, username, password):
        """
        POST https://workai-be.horus.io.vn/api/auth/login
        """
        url = f"{self.base_url}/auth/login"
        payload = {
            "login": username,
            "password": password
        }
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=15)
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get("success"):
                    data = res_data.get("data", {})
                    self.token = data.get("token")
                    self.user_info = data.get("user")
                    self.headers["Authorization"] = f"Bearer {self.token}"
                    
                    # Đồng bộ session sang domain frontend
                    self.sync_web_session(self.token, data.get("token_expires_at"))
                    return True, "Đăng nhập thành công"
                return False, res_data.get("message", "Đăng nhập thất bại")
            return False, f"Lỗi HTTP {response.status_code}"
        except Exception as e:
            return False, f"Lỗi kết nối: {str(e)}"

    def sync_web_session(self, token, expires_at):
        """
        Đồng bộ session sang domain web frontend
        POST https://workai.horus.io.vn/api/auth
        """
        url = "https://workai.horus.io.vn/api/auth"
        payload = {
            "sessionToken": token,
            "expiresAt": expires_at
        }
        try:
            requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        except Exception:
            pass # Lỗi đồng bộ session web không ảnh hưởng đến API calls

    def get_projects(self):
        """
        GET https://workai-be.horus.io.vn/api/projects?pagination=false
        """
        url = f"{self.base_url}/projects"
        params = {"pagination": "false"}
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=15)
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get("success"):
                    # Định dạng lại giống projects.json cũ: [{"name", "code"}]
                    projects = []
                    for item in res_data.get("data", []):
                        projects.append({
                            "name": item.get("name"),
                            "code": item.get("jira_project_key")
                        })
                    return True, projects
                return False, res_data.get("message", "Không thể lấy danh sách dự án")
            return False, f"Lỗi HTTP {response.status_code}"
        except Exception as e:
            return False, f"Lỗi kết nối: {str(e)}"

    def suggest_description(self, project_key, summary):
        """
        POST https://workai-be.horus.io.vn/api/issues/quick-create/suggest-description
        """
        url = f"{self.base_url}/issues/quick-create/suggest-description"
        payload = {
            "project_key": project_key,
            "summary": summary,
            "description": ""
        }
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=60)
            if response.status_code == 200:
                res_data = response.json()
                # API trả về gợi ý description và acceptance_criteria
                if res_data.get("success"):
                    data = res_data.get("data", {})
                    return True, {
                        "description": data.get("description", ""),
                        "acceptance_criteria": data.get("acceptance_criteria", "")
                    }
                # Trả về mặc định nếu API lỗi gợi ý
                return False, res_data.get("message", "Không có gợi ý AI")
            return False, f"Lỗi HTTP {response.status_code}"
        except Exception as e:
            return False, f"Lỗi kết nối: {str(e)}"

    def quick_create_issue(self, project_key, summary, description="", acceptance_criteria="", assignee=None, priority="Medium"):
        """
        POST https://workai-be.horus.io.vn/api/issues/quick-create
        """
        url = f"{self.base_url}/issues/quick-create"
        payload = {
            "project_key": project_key,
            "issue_type": "Story",
            "summary": summary,
            "description": description,
            "acceptance_criteria": acceptance_criteria,
            "assignee": assignee if assignee else (self.user_info.get("username") if self.user_info else None),
            "priority": priority
        }
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=20)
            if response.status_code == 200 or response.status_code == 201:
                res_data = response.json()
                if res_data.get("success"):
                    # Trả về khóa issue được tạo (ví dụ: GRPG-123)
                    data = res_data.get("data", {})
                    return True, data
                return False, res_data.get("message", "Tạo issue thất bại")
            return False, f"Lỗi HTTP {response.status_code}"
        except Exception as e:
            return False, f"Lỗi kết nối: {str(e)}"

    def get_kpi_compliance(self, year, month, user_id=None):
        """
        GET https://workai-be.horus.io.vn/api/kpi/compliance
        """
        url = f"{self.base_url}/kpi/compliance"
        if not user_id and self.user_info:
            user_id = self.user_info.get("id")
        params = {
            "year": str(year),
            "month": str(month),
            "user_id": str(user_id) if user_id else ""
        }
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=15)
            if response.status_code == 200:
                return True, response.json()
            return False, f"Lỗi HTTP {response.status_code}"
        except Exception as e:
            return False, f"Lỗi kết nối: {str(e)}"

    def get_kpi_score(self, year, month, user_id=None):
        """
        GET https://workai-be.horus.io.vn/api/kpi/score
        """
        url = f"{self.base_url}/kpi/score"
        if not user_id and self.user_info:
            user_id = self.user_info.get("id")
        params = {
            "year": str(year),
            "month": str(month),
            "user_id": str(user_id) if user_id else ""
        }
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=15)
            if response.status_code == 200:
                return True, response.json()
            return False, f"Lỗi HTTP {response.status_code}"
        except Exception as e:
            return False, f"Lỗi kết nối: {str(e)}"

    def get_calendar(self, start_date, end_date):
        """
        GET https://workai-be.horus.io.vn/api/calendar
        """
        url = f"{self.base_url}/calendar"
        params = {
            "start_date": start_date,
            "end_date": end_date
        }
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=15)
            if response.status_code == 200:
                return True, response.json()
            return False, f"Lỗi HTTP {response.status_code}"
        except Exception as e:
            return False, f"Lỗi kết nối: {str(e)}"

    def update_issue_summary(self, issue_id, summary):
        """
        Cập nhật summary của một issue (Sử dụng cho sửa KPI)
        PATCH/PUT https://workai-be.horus.io.vn/api/issues/{issue_id}
        """
        url = f"{self.base_url}/issues/{issue_id}"
        payload = {
            "summary": summary
        }
        try:
            response = requests.put(url, json=payload, headers=self.headers, timeout=15)
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get("success"):
                    return True, "Cập nhật thành công"
                return False, res_data.get("message", "Cập nhật thất bại")
            return False, f"Lỗi HTTP {response.status_code}"
        except Exception as e:
            return False, f"Lỗi kết nối: {str(e)}"

    def create_time_allocation(self, issue_id, allocation_date, planned_hours=0.1, sort_order=0):
        """
        POST https://workai-be.horus.io.vn/api/time-allocations
        Thêm issue vào bảng phân bổ thời gian.
        """
        url = f"{self.base_url}/time-allocations"
        payload = {
            "issue_id": int(issue_id),
            "allocation_date": allocation_date,
            "planned_hours": float(planned_hours),
            "sort_order": sort_order
        }
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=15)
            if response.status_code == 200 or response.status_code == 201:
                res_data = response.json()
                if res_data.get("success") or response.status_code == 201:
                    return True, res_data
                return False, res_data.get("message", "Thêm Time Allocation thất bại")
            return False, f"Lỗi HTTP {response.status_code}"
        except Exception as e:
            return False, f"Lỗi kết nối: {str(e)}"

