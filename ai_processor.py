import os
import json

# This function determines which provider to use and calls the appropriate API
def call_ai_provider(provider, api_key, system_prompt, user_prompt, max_output_tokens=None):
    if not api_key:
        raise Exception("Vui lòng cung cấp API Key trong phần Cài đặt.")
        
    if provider == "gemini":
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            gen_config = {}
            if max_output_tokens:
                # Giới hạn tối đa của gemini-1.5-flash là 8192
                gen_config["max_output_tokens"] = min(max_output_tokens, 8192)
            model = genai.GenerativeModel(
                'gemini-1.5-flash',
                system_instruction=system_prompt,
                generation_config=gen_config if gen_config else None
            )
            response = model.generate_content(user_prompt)
            return response.text
        except ImportError:
            raise Exception("Lỗi: Chưa cài đặt thư viện google-generativeai.")
        except Exception as e:
            raise Exception(f"Lỗi gọi Gemini API: {e}")
            
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
    Returns a string of memorytask.md content.
    """
    from datetime import datetime
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    base_prompt = f"""Bạn là trợ lý ảo PM (Project Manager).
Nhiệm vụ của bạn là nhận danh sách tin nhắn và tạo các công việc (Task) theo đúng định dạng được quy định.
Đảm bảo tuân thủ TUYỆT ĐỐI quy tắc Rule B về độ dài tiêu đề (ít nhất 50 ký tự).
LƯU Ý QUAN TRỌNG TỪ NGƯỜI DÙNG: CHỈ TẠO TIÊU ĐỀ (TITLE) CHO CÁC TASK. TUYỆT ĐỐI KHÔNG TẠO PHẦN MÔ TẢ (DESCRIPTION / 1. Background / 2. Objective / 3. Notes / 4. Acceptance Criteria). Hệ thống WorkAI sẽ tự động sinh mô tả dựa trên tiêu đề, vì vậy bạn chỉ cần liệt kê danh sách tiêu đề đầu việc.

Định dạng đầu ra mong muốn của file memorytask.md phải chính xác như sau:

# Daily Tasks — {today_str}

## Task 1
- **Project**: [Mã dự án tương ứng, ví dụ: GRPG]
- **Platform**: [Nền tảng đã cho của task này: rocket hoặc git hoặc email]
- **Title**: [Tiêu đề task - dài ít nhất 50 ký tự]

## Task 2
- **Project**: [Mã dự án tương ứng]
- **Platform**: [Nền tảng đã cho của task này: rocket hoặc git hoặc email]
- **Title**: [Tiêu đề task - dài ít nhất 50 ký tự]

...

TUYỆT ĐỐI không bao gồm trường Duration (Thời lượng).
KHÔNG TRẢ LỜI GIAO TIẾP HOẶC GHI CHÚ GÌ KHÁC NGOÀI NỘI DUNG FORMAT TRÊN.
"""
    system_prompt = base_prompt
    
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
            
        user_prompt += f"Task #{i+1} (Dự án: {t.get('project_code', 'Chưa rõ')}, Nền tảng: {platform}):\n"
        user_prompt += f"- Room: {room_name}\n"
        user_prompt += f"- Nội dung chat: {t.get('text', '')}\n\n"
        
    user_prompt += "\nHãy tạo nội dung file memorytask.md cho các task trên."
    
    result = call_ai_provider(provider, api_key, system_prompt, user_prompt)
    return result

def summarize_raw_chat(raw_data, provider, api_key, projects_list=None, user_name="Chu Văn Mai", user_role="PM", rocket_username=""):
    """
    Takes the raw chat JSON data and uses AI to summarize it into a list of candidate tasks,
    filtering out noise according to the Rules A-H.
    Returns a JSON string array of objects: [{"room_name": "...", "text": "summary...", "sender": "...", "project_code": "..."}]
    """
    short_name = user_name.split()[-1] if user_name else ""
    
    base_prompt = f"""Bạn là trợ lý ảo PM. Nhiệm vụ của bạn là đọc log chat thô và trích xuất ra danh sách các công việc ứng viên (candidate tasks).
Hãy tuân thủ các quy tắc lọc (Rules A-H trong tài liệu đính kèm). ĐẶC BIỆT LƯU Ý QUY TẮC SAU ĐÂY:
- Quy tắc lọc nghiêm ngặt (chỉ lấy tin nhắn do {user_name} gửi hoặc được tag/giao việc trực tiếp) CHỈ áp dụng cho các kênh chat chung (Public Channels).
- ĐỐI VỚI các phòng chat 1-on-1 (Direct Messages - DM) hoặc Nhóm chat riêng tư trao đổi công việc (Private Groups): Hãy trích xuất tất cả các yêu cầu công việc, báo cáo tiến độ, thảo luận công việc từ CẢ HAI PHÍA (người dùng và đối tác chat), không bắt buộc người dùng phải là người gửi hay được tag tên, vì đây là trao đổi trực tiếp phục vụ công việc của chính người dùng.
- ĐỐI VỚI các phòng chat tự note/ghi chú cá nhân (ví dụ: tên phòng chứa 'Onlyme', 'Notes', 'Lưu trữ', 'Ghi chú', hoặc phòng chat với chính mình): Hãy trích xuất TẤT CẢ các tin nhắn ghi chú công việc do người dùng gửi làm đầu việc (task), tuyệt đối không được lọc bỏ.
- ĐỐI VỚI các phòng có tên bắt đầu bằng "Git -" (lịch sử commit Git): Hãy trích xuất TẤT CẢ các commit này thành đầu việc, tuyệt đối không được lọc bỏ và không áp dụng quy tắc lọc người gửi cho các phòng này.
- NẾU cuộc hội thoại diễn ra giữa những người khác trên kênh chung mà {user_name} không tham gia, hoặc chỉ là báo cáo lỗi chung chung của team mà không chỉ định đích danh {user_name} -> BỎ QUA HOÀN TOÀN, TUYỆT ĐỐI KHÔNG TẠO TASK! Không được tự suy diễn kiểu "gián tiếp qua chat".
- MỘT ROOM CÓ THỂ CÓ NHIỀU VIỆC KHÁC NHAU. Hãy TÁCH RIÊNG RẼ từng đầu việc độc lập ra thành các object khác nhau.
- Tóm tắt gọn gàng nội dung của từng đầu việc đó.
- Dựa vào tên room (nhóm chat) hoặc nội dung chat, hãy GÁN mã dự án (project_code) phù hợp nhất từ danh sách dự án (nếu có). Ví dụ: nhóm chat tên "skullhero" thì dự án có thể là game RPG. Nếu không chắc chắn, để rỗng.

LƯU Ý NHẬN DIỆN NGƯỜI DÙNG CHÍNH ĐỂ LỌC:
- Họ và tên người dùng cần quét việc: "{user_name}"
- Tên ngắn của người dùng: "{short_name}"
- Tên tài khoản chat (username): "{rocket_username}"
Hãy linh hoạt nhận diện người dùng. Người dùng có thể xuất hiện trong chat dưới tên đầy đủ "{user_name}", hoặc tên ngắn "{short_name}", hoặc username "{rocket_username}" (hoặc viết tắt/không dấu tương ứng như @{rocket_username if rocket_username else ''}, @{short_name.lower() if short_name else ''}). Nếu người này trực tiếp nhắn tin nói về công việc của mình hoặc được người khác tag/nhắc tên để giao việc, hãy ghi nhận.

Trả về kết quả DƯỚI DẠNG CHUẨN JSON ARRAY, KHÔNG KÈM TEXT NÀO KHÁC. Mỗi object có dạng:
{{
  "room_name": "Tên phòng chat",
  "sender": "Tên người yêu cầu chính",
  "text": "Nội dung tóm tắt của công việc cần làm (viết dạng mô tả ngắn)",
  "project_code": "Mã dự án (ví dụ: GCCF, YQ3) hoặc để rỗng nếu không xác định được",
  "original_chat": "Trích dẫn nguyên văn đoạn chat/commit gốc làm cơ sở sinh ra task này"
}}
"""
    system_prompt = base_prompt + get_system_rules(user_name, user_role)
    # Thêm chỉ thị ánh xạ động cho các quy tắc lọc cứng trong tài liệu quy chế
    system_prompt += f"\n\n--- CẤU HÌNH NGƯỜI DÙNG HIỆN TẠI ---\n- Họ và tên người dùng: {user_name}\n- Vai trò/Chức danh: {user_role}"
    if rocket_username:
        system_prompt += f"\n- Rocket.Chat Username: {rocket_username}"
    system_prompt += f"\nLƯU Ý QUAN TRỌNG: Tất cả các quy tắc lọc trong tài liệu đính kèm có ghi tên 'Chu Văn Mai' sẽ được áp dụng cho người dùng hiện tại là '{user_name}' (username: '{rocket_username}'). Hãy coi họ là đối tượng quét việc chính."
    
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
    Takes the current content of a tab (raw or processed) and a user request,
    and returns the newly edited content and explanation as a JSON string.
    """
    system_prompt = """Bạn là trợ lý ảo PM.
Nhiệm vụ của bạn là chỉnh sửa nội dung văn bản theo yêu cầu của người dùng.
Văn bản hiện tại tuân theo định dạng markdown của các Task:
- Các task được phân chia rõ ràng bởi tiêu đề phụ như '## Task 1', '## Task 2', '## Task 3', v.v.
- Dưới mỗi task sẽ có các trường như '- **Project**:', '- **Platform**:' và '- **Title**:'.

Khi người dùng chỉ định một task (ví dụ: 'sửa task 6 thành...', 'đổi tên dự án task 3...'), bạn phải xác định đúng số thứ tự của task đó để tiến hành chỉnh sửa (ví dụ: 'task 6' là phần nội dung nằm dưới tiêu đề '## Task 6').
Hãy thay đổi chính xác nội dung/trường được yêu cầu (ví dụ: sửa trường Project hoặc sửa trường Title hoặc sửa trường Platform) của đúng task đó.

Yêu cầu cực kỳ quan trọng:
1. Giữ nguyên cấu trúc Markdown tổng thể của toàn bộ tài liệu ban đầu đối với các phần không đổi.
2. TUYỆT ĐỐI không thay đổi, chỉnh sửa hay xóa bất kỳ phần nội dung nào khác của các task không liên quan.
3. Trả về kết quả dưới dạng một đối tượng JSON có đúng 2 trường:
   - "updated_content": Toàn bộ nội dung Markdown hoàn chỉnh của tất cả các task sau khi sửa.
   - "explanation": Chuỗi giải thích chi tiết các thay đổi của bạn dưới dạng liệt kê so sánh các task bị ảnh hưởng theo định dạng:
     * Task #[Số thứ tự]:
       - Cũ: "[Nội dung cũ]"
       - Đã sửa thành: "[Nội dung mới]"
       (Hoặc ghi rõ trạng thái Xóa/Thêm mới/Gộp kèm lý do nếu có).

TUYỆT ĐỐI KHÔNG TRẢ LỜI GIAO TIẾP, GIẢI THÍCH HOẶC GHI CHÚ GÌ KHÁC NGOÀI CHUỖI JSON KẾT QUẢ.
"""
    
    user_prompt = f"YÊU CẦU CỦA NGƯỜI DÙNG: {user_request}\n\nNỘI DUNG HIỆN TẠI:\n{current_content}\n\nHãy sửa NỘI DUNG HIỆN TẠI theo YÊU CẦU CỦA NGƯỜI DÙNG."
    
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
    Returns a list of fixed summaries using AI, based strictly on the reasons.
    """
    base_prompt = """Bạn là trợ lý ảo PM.
Nhiệm vụ của bạn là sửa lại Tiêu đề/Summary của các đầu việc bị đánh giá là "Không đạt".
Hãy tuân thủ tuyệt đối Rule M trong tài liệu đính kèm.

TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON ARRAY CÁC CHUỖI VĂN BẢN (chỉ chứa nội dung đã được sửa). KHÔNG CÓ TEXT NÀO KHÁC.
"""
    system_prompt = base_prompt + get_system_rules(user_name, user_role)
    
    import json
    user_prompt = "Dưới đây là danh sách các task Không đạt:\n\n"
    for i, t in enumerate(tasks):
        user_prompt += f"Task {i+1}:\n"
        user_prompt += f"- Tiêu đề gốc: {t.get('title')}\n"
        user_prompt += f"- Lý do chưa đạt: {t.get('reason')}\n"
        user_prompt += f"- Gợi ý (BỎ QUA): {t.get('suggestion')}\n\n"
        
    user_prompt += "Hãy trả về một mảng JSON các chuỗi (string) tương ứng với nội dung đã được sửa cho từng task theo đúng thứ tự."
    
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
        # Cập nhật kết quả vào tasks
        for i, t in enumerate(tasks):
            if i < len(fixed_list):
                t["fixed_title"] = fixed_list[i]
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
2. Thực hiện các chỉnh sửa tương ứng.
3. Đối với trường hợp gộp các task: giữ lại task A và sửa nó, đổi \"status\" của task B thành \"hide\".
4. TUYỆT ĐỐI KHÔNG TRẢ LỜI GIAO TIẾP, GIẢI THÍCH HOẶC GHI CHÚ GÌ KHÁC NGOÀI CHUỖI JSON KẾT QUẢ.
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
