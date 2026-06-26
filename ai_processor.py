import os
import json

# This function determines which provider to use and calls the appropriate API
def call_ai_provider(provider, api_key, system_prompt, user_prompt, max_output_tokens=None):
    if not api_key:
        raise Exception("Vui lòng cung cấp API Key trong phần Cài đặt.")
        
    if provider == "gemini":
        try:
            import requests as http_requests
            
            # Danh sách các cấu hình (version, model_name) để thử theo thứ tự ưu tiên
            configs_to_try = [
                ("v1beta", "gemini-2.5-flash"),
                ("v1", "gemini-2.5-flash"),
                ("v1beta", "gemini-3.5-flash"),
                ("v1", "gemini-3.5-flash"),
                ("v1beta", "gemini-3.1-flash-lite"),
                ("v1", "gemini-3.1-flash-lite"),
                ("v1beta", "gemini-flash-latest"),
                ("v1beta", "gemini-1.5-flash"),
                ("v1", "gemini-1.5-flash"),
                ("v1beta", "gemini-2.0-flash"),
                ("v1", "gemini-2.0-flash"),
                ("v1beta", "gemini-1.5-pro"),
                ("v1", "gemini-1.5-pro"),
            ]
            
            last_err = None
            debug_logs = []
            for version, model_name in configs_to_try:
                url = f"https://generativelanguage.googleapis.com/{version}/models/{model_name}:generateContent?key={api_key}"
                headers = {
                    "Content-Type": "application/json"
                }
                
                # Nếu là v1, ta ghép system_prompt vào user_prompt để tránh lỗi không hỗ trợ systemInstruction
                if version == "v1" and system_prompt:
                    actual_user_prompt = f"[SYSTEM INSTRUCTIONS]\n{system_prompt}\n\n[USER REQUEST]\n{user_prompt}"
                else:
                    actual_user_prompt = user_prompt
                    
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": actual_user_prompt
                                }
                            ]
                        }
                    ]
                }
                
                # systemInstruction chỉ gửi cho phiên bản v1beta
                if version != "v1" and system_prompt:
                    payload["systemInstruction"] = {
                        "parts": [
                            {
                                "text": system_prompt
                            }
                        ]
                    }
                    
                if max_output_tokens:
                    payload["generationConfig"] = {
                        "maxOutputTokens": min(max_output_tokens, 8192)
                    }
                
                try:
                    debug_logs.append(f"Trying: {version}/{model_name}")
                    resp = http_requests.post(url, json=payload, headers=headers, timeout=15)
                    debug_logs.append(f"  Status: {resp.status_code}")
                    if resp.status_code == 200:
                        res_data = resp.json()
                        candidates = res_data.get("candidates", [])
                        if candidates:
                            text = candidates[0].get("content", {}).get("parts", [])[0].get("text", "")
                            debug_logs.append("  Success!")
                            # Lưu log trước khi return thành công
                            try:
                                with open("f:/prototype/Agent/gemini_test_log.txt", "w", encoding="utf-8") as df:
                                    df.write("\n".join(debug_logs))
                            except Exception:
                                pass
                            return text
                    
                    # Lấy thông tin lỗi chi tiết để ghi nhận
                    try:
                        err_data = resp.json()
                        err_msg = err_data.get("error", {}).get("message", resp.text[:200])
                    except Exception:
                        err_msg = resp.text[:200]
                    last_err = f"Google API Error {resp.status_code}: {err_msg}"
                    debug_logs.append(f"  Error: {err_msg}")
                    
                    # In debug ra terminal để chẩn đoán
                    print(f"[AI Debug] Thử {version}/{model_name} thất bại. Mã lỗi: {resp.status_code}. Chi tiết: {err_msg}")
                    
                    # Nếu lỗi 400 hoặc 404, tiếp tục thử các cấu hình khác
                    if resp.status_code in [400, 404]:
                        continue
                except Exception as req_err:
                    last_err = str(req_err)
                    debug_logs.append(f"  Exception: {str(req_err)}")
            
            # Ghi log ra file khi toàn bộ thất bại
            try:
                with open("f:/prototype/Agent/gemini_test_log.txt", "w", encoding="utf-8") as df:
                    df.write("\n".join(debug_logs))
            except Exception:
                pass
            
            if last_err:
                raise Exception(last_err)
            else:
                raise Exception("Không tìm thấy model Gemini khả dụng nào hoạt động với API Key của bạn. Vui lòng kiểm tra lại xem dự án đã bật 'Generative Language API' trên Google Cloud chưa.")
        except Exception as e:
            raise Exception(f"Lỗi gọi Gemini API: {str(e)}")
            
    elif provider in ["openai", "deepseek"]:
        try:
            from openai import OpenAI
            base_url = "https://api.openai.com/v1"
            model_name = "gpt-4o-mini"
            
            if provider == "deepseek":
                base_url = "https://api.deepseek.com"
                model_name = "deepseek-chat"
                
            client = OpenAI(api_key=api_key, base_url=base_url)
            
            api_params = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
            if max_output_tokens:
                if provider == "openai":
                    # Giới hạn tối đa của gpt-4o-mini là 16384
                    api_params["max_tokens"] = min(max_output_tokens, 16384)
                else:
                    api_params["max_tokens"] = max_output_tokens
            
            response = client.chat.completions.create(**api_params)
            return response.choices[0].message.content
        except ImportError:
            raise Exception("Lỗi: Chưa cài đặt thư viện openai.")
        except Exception as e:
            raise Exception(f"Lỗi gọi {provider} API: {e}")
    else:
        raise Exception("Nhà cung cấp AI không hợp lệ.")

def get_system_rules(user_name=None, user_role=None):
    """Đọc file instructions.md và .agent_rules.md để nhúng vào prompt"""
    # 1. Thử lấy từ thư mục chạy hiện tại (workspace)
    base_dir = os.getcwd()
    inst_path = os.path.join(base_dir, "instructions.md")
    agent_rules_path = os.path.join(base_dir, ".agent_rules.md")
    
    # 2. Nếu không thấy, lấy từ thư mục của module (sys._MEIPASS khi đóng gói)
    if not os.path.exists(inst_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        inst_path = os.path.join(base_dir, "instructions.md")
        agent_rules_path = os.path.join(base_dir, ".agent_rules.md")
        
    rules = ""
    if os.path.exists(inst_path):
        with open(inst_path, "r", encoding="utf-8") as f:
            rules += "\n--- QUY TẮC TỪ instructions.md ---\n" + f.read()
            
    if os.path.exists(agent_rules_path):
        with open(agent_rules_path, "r", encoding="utf-8") as f:
            rules += "\n--- QUY TẮC TỪ .agent_rules.md ---\n" + f.read()
            
    if user_name:
        # Thay thế động tên 'Chu Văn Mai' trong các quy tắc thành tên người dùng hiện tại
        rules = rules.replace("Chu Văn Mai", user_name)
        if user_name != "Chu Văn Mai":
            rules = rules.replace("🙈🙉🙊", "")
        
    if user_role:
        # Thay thế động vai trò/chức danh
        rules = rules.replace("Team Lead Game Designer & Concurrently PM (Project Manager)", user_role)
        rules = rules.replace("Team Lead Game Designer & PM", user_role)
        
    return rules

def generate_tasks(raw_tasks, provider, api_key):
    """
    Takes raw tasks array and uses AI to format them into the required structure.
    Returns a JSON string of formatted tasks.
    """
    from datetime import datetime
    import json
    import os
    
    projects_list = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    projects_file = os.path.join(base_dir, "projects.json")
    if os.path.exists(projects_file):
        try:
            with open(projects_file, "r", encoding="utf-8") as f:
                projects_list = json.load(f)
        except:
            pass
            
    project_options = ", ".join([f"{p.get('code')} ({p.get('name')})" for p in projects_list])
    
    system_prompt = f"""Bạn là trợ lý ảo PM (Project Manager).
Nhiệm vụ của bạn là nhận danh sách tin nhắn và tạo các công việc (Task) dưới dạng một JSON Array duy nhất.

## DANH SÁCH DỰ ÁN HỢP LỆ (PROJECT CODES):
Các mã dự án hợp lệ bạn được phép sử dụng:
{project_options}

## QUY TẮC ĐẶT TIÊU ĐỀ (TITLE) (BẮT BUỘC):
- Tiêu đề phải dài ít nhất 50 ký tự.
- Công thức: `[Hành động] - [Mục tiêu]`
- Ví dụ: `[Chỉ đạo] - Triển khai thiết kế giao diện màn hình đăng nhập cho ứng dụng mobile`

## QUY TẮC SINH DESCRIPTION (BẮT BUỘC):
Description của mỗi task PHẢI được sinh dựa trên Title của task đó và PHẢI có ĐỦ 3 MỤC sau (giữ nguyên tiêu đề các mục bằng tiếng Anh như bên dưới):
1. Background:
   - Bối cảnh công việc: Tại sao task này cần thực hiện?
   - Mô tả ngắn gọn tình huống hoặc yêu cầu từ đâu.
2. Objective:
   - Mục tiêu cụ thể cần đạt được khi hoàn thành task này.
   - Viết rõ kết quả mong đợi (deliverable).
3. Notes:
   - Các lưu ý quan trọng, ràng buộc, điều kiện đặc biệt. Nếu không có, ghi "Không có ghi chú thêm."

## QUY TẮC SINH ACCEPTANCE CRITERIA (BẮT BUỘC):
Tiêu chí nghiệm thu (Acceptance Criteria) PHẢI được sinh dựa trên Title và Description của task.
Mỗi tiêu chí là 1 dòng bắt đầu bằng dấu "- ", mô tả điều kiện cụ thể để xác nhận task đã hoàn thành. Yêu cầu:
- Tối thiểu 2 tiêu chí, tối đa 5 tiêu chí.
- Mỗi tiêu chí phải đo lường được (measurable) hoặc kiểm chứng được (verifiable).
- Viết bằng tiếng Việt (trừ thuật ngữ kỹ thuật).
- KHÔNG viết chung chung kiểu "Hoàn thành task" — phải cụ thể.

## ĐỊNH DẠNG ĐẦU RA MONG MUỐN:
Bạn BẮT BUỘC phải trả về một JSON Array duy nhất chứa các đối tượng có cấu trúc như sau. Tuyệt đối không bao gồm bất kỳ lời dẫn hay văn bản giải thích nào ngoài khối JSON.
[
  {{
    "project": "Mã dự án (chọn từ danh sách hợp lệ trên, hoặc sử dụng mã dự án mặc định của task)",
    "platform": "nền tảng của task: rocket hoặc git hoặc email",
    "title": "Tiêu đề task (>= 50 ký tự, format `[Hành động] - [Mục tiêu]`)",
    "description": "1. Background:\\n[Nội dung bối cảnh]\\n\\n2. Objective:\\n[Nội dung mục tiêu]\\n\\n3. Notes:\\n[Nội dung ghi chú]",
    "acceptance_criteria": "- [Tiêu chí 1]\\n- [Tiêu chí 2]"
  }}
]
"""
    
    # We will build the user prompt from raw_tasks
    user_prompt = "Dưới đây là danh sách các tin nhắn cần chuyển thành Task:\n\n"
    for i, t in enumerate(raw_tasks):
        room_name = t.get('room_name', '')
        if room_name.startswith("Git -"):
            platform = "git"
        elif room_name.startswith("Email:"):
            platform = "email"
        else:
            platform = "rocket"
            
        user_prompt += f"Task #{i+1} (Dự án gợi ý: {t.get('project_code', 'Chưa rõ')}, Nền tảng: {platform}):\n"
        user_prompt += f"- Room: {room_name}\n"
        user_prompt += f"- Nội dung chat: {t.get('text', '')}\n\n"
        
    user_prompt += "\nHãy tạo JSON Array cho các task trên."
    
    result = call_ai_provider(provider, api_key, system_prompt, user_prompt)
    result = result.strip()
    if result.startswith("```json"):
        result = result[7:]
    elif result.startswith("```"):
        result = result[3:]
    if result.endswith("```"):
        result = result[:-3]
    return result.strip()

def summarize_raw_chat(raw_data, provider, api_key, projects_list=None, user_name="Chu Văn Mai", user_role="PM", rocket_username=""):
    """
    Takes the raw chat JSON data and uses AI to summarize it into a list of candidate tasks,
    filtering out noise according to the Rules A-H.
    Returns a JSON string array of objects: [{"room_name": "...", "text": "summary...", "sender": "...", "project_code": "..."}]
    """
    # Clean emojis from user_name for AI prompt matching
    clean_user_name = user_name.replace("🙈🙉🙊", "").strip()
    short_name = clean_user_name.split()[-1] if clean_user_name else ""
    
    base_prompt = f"""Bạn là trợ lý ảo PM. Nhiệm vụ của bạn là đọc log chat thô và trích xuất ra danh sách các công việc ứng viên (candidate tasks) LIÊN QUAN TRỰC TIẾP đến người dùng.

Họ và tên người dùng cần quét việc: "{clean_user_name}"
Tên ngắn của người dùng: "{short_name}"
Tên tài khoản chat (username): "{rocket_username}"

## QUY TẮC PHÂN TÍCH & LỌC NGHIÊM NGẶT (BẮT BUỘC):
Bạn PHẢI phân tích kỹ từng tin nhắn và cuộc hội thoại để lọc bỏ các tin nhắn không liên quan:
1. **Đối với Kênh chat chung (Public Channels) và Nhóm chat riêng tư nhiều người (Private Groups)**:
   - Trích xuất các tin nhắn do chính "{clean_user_name}" (hoặc username "{rocket_username}") gửi.
   - HOẶC các tin nhắn của người khác gửi có nhắc tên/tag trực tiếp đến "{clean_user_name}", "{short_name}", hoặc "{rocket_username}" (ví dụ: "@maicv check...", "Mai ơi...", "Nhờ sếp Mai...") để giao việc hoặc hỏi ý kiến trực tiếp.
   - ĐẶC BIỆT: Nếu "{clean_user_name}" có tham gia nhắn tin trao đổi trực tiếp trong một cuộc hội thoại/luồng thảo luận, hãy đọc và phân tích toàn bộ các tin nhắn trả lời trực tiếp hoặc tin nhắn liền kề có liên quan trong luồng thảo luận đó (ngay cả khi người khác phản hồi cho "{clean_user_name}" mà quên tag tên) để trích xuất đầy đủ và chính xác ngữ cảnh công việc.
   - TUYỆT ĐỐI KHÔNG trích xuất tin nhắn của những người khác tự bàn thảo/giao việc với nhau mà không có sự tham gia của bạn và không nhắc tên hay tag người dùng chính.
2. **Đối với các phòng chat 1-on-1 (Direct Messages - DM)**:
   - Trích xuất tất cả các yêu cầu công việc, thảo luận, báo cáo tiến độ từ CẢ HAI PHÍA (người dùng và đối tác chat) vì đây là trao đổi trực tiếp phục vụ công việc của chính người dùng.
3. **Đối với phòng tự note/ghi chú cá nhân (Onlyme, Notes, Ghi chú, Lưu trữ)**:
   - Trích xuất TẤT CẢ tin nhắn do người dùng gửi.
   - Trích xuất các ghi chú công việc.
4. **Đối với phòng Git commit ("Git -")**:
   - Trích xuất tất cả các commit. Không áp dụng bộ lọc người gửi ở đây.

## NGOẠI LỆ & RÀNG BUỘC PHẢI TUÂN THỦ (ĐỂ TRÁNH LỌC SAI):
- **Cảnh báo và Báo cáo tự động (Auto alerts/reports)**: TUYỆT ĐỐI BỎ QUA toàn bộ các tin nhắn cảnh báo tự động của bot (ví dụ: báo cáo drop rate tự động từ bot 'Admin data', báo cáo điểm danh tự động). Chỉ trích xuất nếu có người nhắn tin trực tiếp và nhắc tên bạn để xử lý cảnh báo đó.
- **Kênh thông báo đơn từ/lịch họp (Notification/Petition)**: CHỈ trích xuất nếu đơn từ đó tag hoặc nhắc trực tiếp đến tên/username của bạn để yêu cầu bạn phê duyệt. Nếu đơn từ tag người quản lý khác (ví dụ: tag @Khanhnv, @Thangtm) mà không tag bạn -> BỎ QUA HOÀN TOÀN, không được tự động nhận việc.
- **Hội thoại của người khác**: Nếu những người khác trò chuyện/báo cáo công việc với nhau trong nhóm mà không tag bạn -> BỎ QUA HOÀN TOÀN, TUYỆT ĐỐI KHÔNG tạo task.

NẾU người dùng không nhắn tin, không được nhắc tên, không được tag trực tiếp trong hội thoại hoặc thông báo -> BỎ QUA HOÀN TOÀN, TUYỆT ĐỐI KHÔNG TẠO TASK!

- **QUY TẮC TÁCH BIỆT TASK (BẮT BUỘC)**:
  + MỘT TIN NHẮN HOẶC MỘT ROOM CÓ THỂ CHỨA NHIỀU CÔNG VIỆC KHÁC NHAU. Bạn BẮT BUỘC phải tách riêng rẽ từng đầu việc độc lập ra thành các đối tượng task khác nhau.
  + ĐẶC BIỆT: Khi có tin nhắn giao việc hoặc phân công nhiệm vụ cho nhiều nhân sự khác nhau trong cùng một dòng chat (Ví dụ: '@Tandm làm A; @Vuongdm làm B; @Dungnd1 làm C'), bạn phải TÁCH THÀNH CÁC TASK RIÊNG BIỆT cho từng người. Không được gộp chung tất cả vào làm một task duy nhất.

- **QUY TẮC BIÊN TẬP NỘI DUNG (TRƯỜNG 'text')**:
  + Bạn phải biên tập, viết lại trường `text` của công việc một cách gọn gàng, súc tích và chuyên nghiệp.
  + Loại bỏ toàn bộ các tag tên `@username`, emoji thừa thãi khỏi nội dung công việc.
  + Viết rõ hành động cụ thể cần làm (Ví dụ thay vì để nguyên văn '@Tandm đẩy map mới lên để setup quái' hãy viết lại thành 'Chỉ đạo đẩy map mới lên hệ thống để chuẩn bị cài đặt quái').

Hãy linh hoạt nhận diện người dùng chính thông qua tên "{clean_user_name}", tên ngắn "{short_name}", hoặc username "{rocket_username}" (hoặc viết tắt/không dấu tương ứng như @{rocket_username if rocket_username else ''}, @{short_name.lower() if short_name else ''}).

Trả về kết quả DƯỚI DẠNG CHUẨN JSON ARRAY, KHÔNG KÈM TEXT NÀO KHÁC. Mỗi object có dạng:
{{
  "room_name": "Tên phòng chat",
  "sender": "Tên người yêu cầu chính",
  "text": "Nội dung tóm tắt của công việc đã được tách và biên tập sạch sẽ (không chứa emoji, không chứa tag @username)",
  "project_code": "Mã dự án (ví dụ: GRPG, GSSP) hoặc để rỗng nếu không xác định được",
  "original_chat": "Trích dẫn nguyên văn đoạn chat/commit gốc làm cơ sở sinh ra task này (Giữ nguyên văn có emoji và tag ở đây để đối chiếu)"
}}
"""
    system_prompt = base_prompt + get_system_rules(clean_user_name, user_role)
    system_prompt += f"\n\n--- CẤU HÌNH NGƯỜI DÙNG HIỆN TẠI ---\n- Họ và tên người dùng: {clean_user_name}\n- Vai trò/Chức danh: {user_role}"
    if rocket_username:
        system_prompt += f"\n- Rocket.Chat Username: {rocket_username}"
    system_prompt += f"\nLƯU Ý QUAN TRỌNG: Tất cả các quy tắc lọc trong tài liệu đính kèm có ghi tên 'Chu Văn Mai' sẽ được áp dụng cho người dùng hiện tại là '{clean_user_name}' (username: '{rocket_username}'). Hãy coi họ là đối tượng quét việc chính."
    system_prompt += f"""

==================================================
⚠️ LƯU Ý QUAN TRỌNG VÀ BẮT BUỘC (ĐÈ LÊN TẤT CẢ QUY TẮC KHÁC):
1. Bạn CHỈ ĐƯỢC PHÉP trích xuất công việc liên quan trực tiếp đến {clean_user_name} (chính {clean_user_name} nhắn, hoặc người khác tag/nhắc tên {clean_user_name} / {short_name} / {rocket_username} đích danh).
2. TUYỆT ĐỐI KHÔNG trích xuất tin nhắn của người khác trò chuyện/bàn giao việc cho nhau trong nhóm chat chung/riêng tư nếu không tag hay nhắc tên bạn.
3. TUYỆT ĐỐI KHÔNG trích xuất các tin nhắn thông báo tự động (drop rate, cảnh báo camera, đơn từ của người khác trong phòng PMNotification/PMNhansu gửi cho quản lý khác mà không tag bạn).
4. KHÔNG tự suy diễn công việc dựa trên ngữ cảnh nếu không có yêu cầu trực tiếp gửi đến {clean_user_name}.
Nếu vi phạm các điều trên, bộ lọc sẽ thất bại. Hãy kiểm tra lại từng task trước khi xuất kết quả!
==================================================
"""
    
    user_prompt = "Danh sách các dự án hiện có trên WorkAI:\n"
    if projects_list:
        for p in projects_list:
            user_prompt += f"- {p.get('name')} (Mã: {p.get('code')})\n"
    else:
        user_prompt += "(Không có dữ liệu dự án)\n"
        
    user_prompt += "\nDưới đây là log chat thô:\n\n"
    for room in raw_data:
        room_name = room.get("room_name", "Unknown")
        for msg in room.get("messages", []):
            user_prompt += f"[{room_name}] {msg.get('sender')}: {msg.get('text')}\n"
            
    user_prompt += "\nHãy trích xuất và tóm tắt thành các đầu việc (trả về đúng định dạng JSON Array)."
    
    result = call_ai_provider(provider, api_key, system_prompt, user_prompt)
    
    result = result.strip()
    if result.startswith("```json"):
        result = result[7:]
    elif result.startswith("```"):
        result = result[3:]
    if result.endswith("```"):
        result = result[:-3]
        
    return result.strip()

def edit_task_with_ai(current_content, user_request, provider, api_key):
    """
    Takes the current tasks (JSON string) and a user request,
    and returns the newly edited tasks JSON array and explanation as a JSON string.
    """
    system_prompt = """Bạn là trợ lý ảo PM.
Nhiệm vụ của bạn là chỉnh sửa danh sách các công việc (dạng JSON Array) theo yêu cầu của người dùng.

JSON đầu vào hiện tại chứa danh sách các task với các trường:
- `project`: Mã dự án (ví dụ: GRPG)
- `platform`: Nền tảng (rocket, git, email)
- `title`: Tiêu đề task (phải dài >= 50 ký tự, format `[Action] - [Objective]`)
- `description`: Mô tả chi tiết (bắt buộc gồm 3 phần: Background, Objective, Notes)
- `acceptance_criteria`: Tiêu chí nghiệm thu (danh sách dòng bắt đầu bằng "- ")

Khi người dùng yêu cầu thay đổi (ví dụ: "sửa task 1 thành...", "thêm task mới...", "xóa task 3", "đổi dự án của task 2 sang GSSP"), bạn hãy chỉnh sửa tương ứng trong danh sách JSON.

Yêu cầu cực kỳ quan trọng:
1. Giữ nguyên các task không bị yêu cầu thay đổi.
2. Khi sửa đổi hoặc tạo mới Title, phải tuân thủ nghiêm ngặt quy tắc: dài ít nhất 50 ký tự, định dạng `[Hành động] - [Mục tiêu]`.
3. Khi sửa đổi hoặc tạo mới Description, phải đủ 3 mục (Background, Objective, Notes).
4. Khi sửa đổi hoặc tạo mới Acceptance Criteria, phải gồm từ 2 đến 5 dòng bắt đầu bằng dấu "- ".
5. Trả về kết quả dưới dạng một đối tượng JSON có đúng 2 trường:
   - "updated_content": Chuỗi JSON của mảng tasks đã cập nhật (JSON stringified array).
   - "explanation": Chuỗi giải thích chi tiết các thay đổi của bạn dưới dạng liệt kê so sánh các task bị ảnh hưởng.
   
TUYỆT ĐỐI KHÔNG TRẢ LỜI GIAO TIẾP, GIẢI THÍCH HOẶC GHI CHÚ GÌ KHÁC NGOÀI CHUỖI JSON KẾT QUẢ.
"""
    
    user_prompt = f"YÊU CẦU CỦA NGƯỜI DÙNG: {user_request}\n\nNỘI DUNG HIỆN TẠI (JSON):\n{current_content}\n\nHãy sửa NỘI DUNG HIỆN TẠI theo YÊU CẦU CỦA NGƯỜI DÙNG."
    
    result = call_ai_provider(provider, api_key, system_prompt, user_prompt)
    result = result.strip()
    if result.startswith("```json"):
        result = result[7:]
    elif result.startswith("```"):
        result = result[3:]
    if result.endswith("```"):
        result = result[:-3]
    return result.strip()

def fix_kpi_tasks(tasks, provider, api_key, user_name="Chu Văn Mai", user_role="PM"):
    """
    Takes a list of failed KPI tasks: [{"title": "...", "reason": "...", "suggestion": "..."}]
    Returns a list of fixed summaries using AI, based strictly on Rule B naming conventions.
    """
    base_prompt = """Bạn là trợ lý ảo PM.
Nhiệm vụ của bạn là sửa lại Tiêu đề/Summary của các đầu việc bị đánh giá là "Không đạt" trên hệ thống KPI.

## QUY TẮC BẮT BUỘC KHI SỬA TIÊU ĐỀ (Rule B):
1. **Công thức đặt tên**: `[Làm gì / Hành động cụ thể] - [Để làm gì / Mục tiêu cụ thể]`
2. **Độ dài tối thiểu**: Tiêu đề phải dài ít nhất **50 ký tự** (kể cả khoảng trắng). Mở rộng phần hành động và mục tiêu nếu cần.
3. **Viết bằng tiếng Việt** (trừ các thuật ngữ kỹ thuật tiếng Anh phổ biến).
4. **Ví dụ đúng**:
   - "Khắc phục lỗi hiển thị ảnh sản phẩm IAP trên iOS - Đảm bảo thông tin gói IAP xuất hiện đầy đủ và chính xác trên App Store"
   - "Thiết kế và triển khai giao diện màn hình đăng nhập - Phục vụ tính năng xác thực người dùng trên ứng dụng mobile"
   - "Kiểm tra và xác thực tính toàn vẹn UI/UX cùng logic vận hành - Đảm bảo hệ thống Pet hoạt động ổn định sau khi tích hợp"

## TUYỆT ĐỐI KHÔNG ĐƯỢC LÀM:
- **KHÔNG ĐƯỢC** sử dụng nội dung gợi ý của hệ thống KPI (ví dụ: "Viết lại summary dài hơn, ví dụ: ...") làm tiêu đề mới. Đó chỉ là chỉ dẫn meta, KHÔNG PHẢI nội dung tiêu đề.
- **KHÔNG ĐƯỢC** trả về tiêu đề bằng 100% tiếng Anh. Phải dùng tiếng Việt hoặc mix tiếng Việt + thuật ngữ kỹ thuật.
- **KHÔNG ĐƯỢC** copy nguyên văn trường "Gợi ý" vào kết quả.
- **KHÔNG ĐƯỢC** bắt đầu tiêu đề bằng "Viết lại...", "Sửa lại...", "Cần viết..." hoặc các chỉ dẫn meta tương tự.

## CÁCH XỬ LÝ:
- Đọc tiêu đề gốc (có chứa JIRA Key ở đầu, ví dụ "GAE-1907 - ..."). Phần sau dấu " - " là nội dung summary thực tế.
- Dựa trên NỘI DUNG GỐC CỦA TIÊU ĐỀ, viết lại theo đúng công thức Rule B.
- GIỮ NGUYÊN ý nghĩa công việc gốc, chỉ mở rộng và format lại cho đúng chuẩn.
- KHÔNG thêm JIRA Key vào kết quả trả về (chỉ trả về phần summary thuần).

TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON ARRAY CÁC CHUỖI VĂN BẢN (chỉ chứa nội dung summary đã được sửa). KHÔNG CÓ TEXT NÀO KHÁC.
"""
    system_prompt = base_prompt + get_system_rules(user_name, user_role)
    
    import json
    user_prompt = "Dưới đây là danh sách các task Không đạt cần sửa tiêu đề:\n\n"
    for i, t in enumerate(tasks):
        # Tách JIRA key khỏi title để hiển thị rõ ràng
        raw_title = t.get('title', '')
        user_prompt += f"Task {i+1}:\n"
        user_prompt += f"- Tiêu đề gốc (gồm JIRA Key): {raw_title}\n"
        user_prompt += f"- Lý do chưa đạt: {t.get('reason')}\n"
        user_prompt += f"- [KHÔNG DÙNG LÀM TIÊU ĐỀ] Gợi ý hệ thống (chỉ tham khảo): {t.get('suggestion')}\n\n"
        
    user_prompt += """Hãy trả về một mảng JSON các chuỗi (string) tương ứng với TIÊU ĐỀ ĐÃ ĐƯỢC SỬA cho từng task theo đúng thứ tự.
LƯU Ý: Mỗi chuỗi trả về phải là tiêu đề hoàn chỉnh theo Rule B (>= 50 ký tự, format [Hành động] - [Mục tiêu]), KHÔNG chứa JIRA Key, KHÔNG chứa gợi ý meta."""
    
    result = call_ai_provider(provider, api_key, system_prompt, user_prompt)
    
    result = result.strip()
    if result.startswith("```json"):
        result = result[7:]
    elif result.startswith("```"):
        result = result[3:]
    if result.endswith("```"):
        result = result[:-3]
        
    try:
        fixed_list = json.loads(result.strip())
        
        # Validation: kiểm tra output AI không phải là suggestion text
        INVALID_PREFIXES = ["viết lại", "sửa lại", "cần viết", "write a longer", "rewrite"]
        
        for i, t in enumerate(tasks):
            if i < len(fixed_list):
                fixed = fixed_list[i]
                # Kiểm tra xem AI có copy suggestion text không
                fixed_lower = fixed.lower().strip()
                is_invalid = any(fixed_lower.startswith(prefix) for prefix in INVALID_PREFIXES)
                
                if is_invalid:
                    # AI đã copy suggestion thay vì sửa → giữ nguyên tiêu đề gốc
                    print(f"[WARN] Task {i+1}: AI trả về gợi ý meta thay vì tiêu đề. Giữ nguyên tiêu đề gốc.")
                    t["fixed_title"] = t["title"]
                else:
                    t["fixed_title"] = fixed
            else:
                t["fixed_title"] = t["title"]
        return tasks
    except Exception as e:
        print(f"JSON Parse error in fix_kpi_tasks: {e}")
        return tasks

def edit_raw_tasks_with_ai(current_json_str, user_request, provider, api_key):
    """
    Takes the JSON string representing the current list of raw tasks and the user instruction,
    and returns the updated list of raw tasks and explanation as a JSON string wrapper.
    """
    base_dir = os.getcwd()
    projects_file = os.path.join(base_dir, "projects.json")
    projects_info = ""
    if os.path.exists(projects_file):
        try:
            with open(projects_file, "r", encoding="utf-8") as pf:
                projects_list = json.load(pf)
                projects_info = "Danh sách các dự án hiện có trên WorkAI:\n"
                for p in projects_list:
                    projects_info += f"- {p.get('name')} (Mã dự án: {p.get('code')})\n"
        except Exception:
            pass

    system_prompt = f"""Bạn là trợ lý ảo PM.
Nhiệm vụ của bạn là chỉnh sửa danh sách các công việc thô (JSON Array) theo yêu cầu của người dùng.
Dữ liệu đầu vào là một chuỗi JSON chứa danh sách các công việc thô có các thuộc tính:
- "id": Mã định danh duy nhất của công việc (Giữ nguyên, không được tự ý thay đổi).
- "status": Trạng thái của công việc ("active" hoặc "hide"). Nếu người dùng yêu cầu xóa hoặc loại bỏ một công việc, hãy đặt "status" thành "hide".
- "room_name": Tên phòng chat chứa đoạn chat gốc.
- "sender": Tên người gửi tin nhắn thô.
- "text": Tóm tắt nội dung thô của công việc (Người dùng có thể yêu cầu sửa nội dung này).
- "project_code": Mã dự án (Ví dụ: GRPG, GCCF). Người dùng có thể yêu cầu gán dự án cho một hoặc nhiều công việc.
- "original_chat": Đoạn chat gốc làm cơ sở.

{projects_info}

Bạn phải luôn trả về một đối tượng JSON lớn chứa thông tin giải thích ("explanation"), chế độ xử lý ("mode") và dữ liệu cập nhật tương ứng. Cụ thể có 2 chế độ xử lý tùy vào yêu cầu của người dùng:

### CHẾ ĐỘ 1 - SỬA NHỎ (mặc định):
Khi yêu cầu là sửa nhỏ (gán dự án, sửa text, xóa, gộp - tạo ít hơn 10 task mới):
Đối tượng JSON trả về dạng:
{{
  "explanation": "Chuỗi giải thích chi tiết các thay đổi của bạn dưới dạng liệt kê so sánh các task bị ảnh hưởng theo định dạng:\\n* Task #[Số thứ tự]:\\n  - Cũ: \\"[Nội dung cũ hoặc Dự án cũ]\\"[Mã dự án nếu đổi]\\n  - Đã sửa thành: \\"[Nội dung mới hoặc Dự án mới]\\"[Mã dự án nếu đổi]\\n  (Hoặc ghi rõ trạng thái Xóa/Gộp kèm lý do nếu có).",
  "mode": "full",
  "updated_tasks": [
     ... mảng JSON đầy đủ tất cả các phần tử sau khi đã sửa đổi (giữ nguyên cấu trúc ban đầu, chỉ cập nhật nội dung) ...
  ]
}}

### CHẾ ĐỘ 2 - TÁCH/TẠO NHIỀU TASK MỚI:
Khi yêu cầu là TÁCH 1 task thành nhiều task (>=10 task mới), hoặc tạo hàng loạt task mới:
Đối tượng JSON trả về dạng:
{{
  "explanation": "Chuỗi giải thích chi tiết việc tách/tạo các task mới (ví dụ tách từ task nào thành bao nhiêu task mới, liệt kê tóm tắt).",
  "mode": "patch",
  "hide_ids": ["id_task_goc_can_an"],
  "new_tasks": [
    {{"room_name": "...", "sender": "...", "text": "...", "project_code": "...", "original_chat": "..."}},
    ...
  ]
}}
- "hide_ids": Danh sách ID của các task gốc cần ẩn (set status = hide).
- "new_tasks": Danh sách các task MỚI cần tạo (KHÔNG cần trường id và status, hệ thống sẽ tự sinh).

Quy tắc chung:
1. Hãy xác định đúng các công việc cần sửa (Dựa trên số thứ tự 1-indexed tương ứng với vị trí các công việc có status \"active\" trong mảng ban đầu, hoặc dựa trên tên sender, tên room chat, v.v.).
2. Khi sửa đổi trường "text" (Nội dung tóm tắt công việc) hoặc tạo mới trong "new_tasks", bạn BẮT BUỘC phải tuân thủ nghiêm ngặt Rule M về đặt tên đầu việc: Định dạng `[Action] - [Objective]` dài tối thiểu 50 ký tự (Ví dụ: `[Research] - Tìm hiểu và phân tích cấu trúc mã nguồn dự án CompanySkills để tích hợp vào Athena`). Tuyệt đối không sinh ra tiêu đề ngắn cẩu thả hoặc thiếu tag hành động `[Action]`.
3. Thực hiện các chỉnh sửa tương ứng.
4. Đối với trường hợp gộp các task: giữ lại task A và sửa nó, đổi \"status\" của task B thành \"hide\".
5. TUYỆT ĐỐI KHÔNG TRẢ LỜI GIAO TIẾP, GIẢI THÍCH HOẶC GHI CHÚ GÌ KHÁC NGOÀI CHUỖI JSON KẾT QUẢ.
"""
    
    user_prompt = f"YÊU CẦU CỦA NGƯỜI DÙNG: {user_request}\n\nDANH SÁCH TASK HIỆN TẠI (JSON):\n{current_json_str}\n\nHãy chỉnh sửa danh sách trên theo yêu cầu của người dùng và trả về kết quả JSON (dùng Chế độ 1 hoặc Chế độ 2 tùy tình huống)."
    
    result = call_ai_provider(provider, api_key, system_prompt, user_prompt, max_output_tokens=65536)
    result = result.strip()
    if result.startswith("```json"):
        result = result[7:]
    elif result.startswith("```"):
        result = result[3:]
    if result.endswith("```"):
        result = result[:-3]
    return result.strip()
