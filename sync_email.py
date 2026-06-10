# -*- coding: utf-8 -*-
import os
import json
import imaplib
import email
from email.header import decode_header
import email.utils
import re
import html
import ssl
from datetime import datetime, timezone

# Ánh xạ tên tháng sang tiếng Anh độc lập với locale hệ thống
MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
}

import sys
def load_env(path=".env"):
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
        path = os.path.join(base_dir, ".env")
    env = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

def decode_mime_words(s):
    if not s:
        return ""
    try:
        parts = decode_header(s)
        decoded = []
        for word, encoding in parts:
            if isinstance(word, bytes):
                decoded.append(word.decode(encoding or 'utf-8', errors='replace'))
            else:
                decoded.append(str(word))
        return "".join(decoded)
    except Exception:
        return str(s)

def parse_email_date(date_str):
    if not date_str:
        return None
    try:
        return email.utils.parsedate_to_datetime(date_str)
    except Exception:
        return None

def clean_html(raw_html):
    if not raw_html:
        return ""
    # Loại bỏ thẻ style và script
    cleanr = re.compile('<style.*?>.*?</style>', re.DOTALL | re.IGNORECASE)
    raw_html = re.sub(cleanr, '', raw_html)
    cleanr = re.compile('<script.*?>.*?</script>', re.DOTALL | re.IGNORECASE)
    raw_html = re.sub(cleanr, '', raw_html)
    
    # Loại bỏ tất cả các thẻ HTML khác
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    
    return html.unescape(cleantext).strip()

def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    charset = part.get_content_charset() or 'utf-8'
                    payload = part.get_payload(decode=True)
                    body += payload.decode(charset, errors='replace')
                except Exception:
                    pass
            elif content_type == "text/html" and not body and "attachment" not in content_disposition:
                try:
                    charset = part.get_content_charset() or 'utf-8'
                    payload = part.get_payload(decode=True)
                    html_content = payload.decode(charset, errors='replace')
                    body = clean_html(html_content)
                except Exception:
                    pass
    else:
        content_type = msg.get_content_type()
        if content_type in ["text/plain", "text/html"]:
            try:
                charset = msg.get_content_charset() or 'utf-8'
                payload = msg.get_payload(decode=True)
                text = payload.decode(charset, errors='replace')
                if content_type == "text/html":
                    body = clean_html(text)
                else:
                    body = text
            except Exception:
                pass
    return body.strip()

def normalize_subject(subject):
    if not subject:
        return "No Subject"
    # Chuẩn hóa về chữ thường
    sub = subject.strip()
    # Loại bỏ Re:, Fw:, Fwd:, Re-... ở đầu tiêu đề
    regex = re.compile(r'^(re|fw|fwd|reply|forward|tr|trả lời|chuyển tiếp):\s*', re.IGNORECASE)
    while regex.match(sub):
        sub = regex.sub('', sub)
    return sub.strip()

def main(last_sync_ms=None):
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Đọc cấu hình từ config.json
    imap_server = ""
    email_user = ""
    email_pass = ""
    config_file = os.path.join(base_dir, "config.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                email_user = config.get("email_user", "")
                email_pass = config.get("email_pass", "")
                
                # Tìm IMAP server trong danh sách platforms
                platforms = config.get("platforms", [])
                for p in platforms:
                    if p.get("type") == "email":
                        imap_server = p.get("url", "")
                        if p.get("uid") and not email_user:
                            email_user = p.get("uid")
                        if p.get("token") and not email_pass:
                            email_pass = p.get("token")
        except Exception as e:
            print(f"[WARNING] Failed to parse config.json in email sync: {e}")

    # 2. Đọc dự phòng từ .env
    env = load_env()
    if not imap_server: imap_server = env.get("EMAIL_IMAP_SERVER", "")
    if not email_user: email_user = env.get("EMAIL_USER", "")
    if not email_pass: email_pass = env.get("EMAIL_PASS", "")

    if not imap_server or not email_user or not email_pass:
        print("[WARNING] Email (IMAP) credentials/server details are missing. Skipping Email sync.")
        return

    # Xác định mốc thời gian lọc email
    local_tz = datetime.now().astimezone().tzinfo
    if last_sync_ms:
        # Giảm 2 phút (120,000 ms) buffer chống lệch múi giờ/lệch đồng hồ client-server
        start_ms = last_sync_ms - 120000
        start_dt = datetime.fromtimestamp(start_ms / 1000.0, tz=timezone.utc)
    else:
        # Mặc định từ 0h sáng nay
        start_dt_local = datetime.now(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        start_dt = start_dt_local.astimezone(timezone.utc)

    # Đổi sang ngày tháng IMAP format (DD-Mon-YYYY) sử dụng tên tháng tiếng Anh
    day = start_dt.day
    month_name = MONTH_NAMES[start_dt.month]
    year = start_dt.year
    imap_date_str = f"{day:02d}-{month_name}-{year}"

    print(f"Email IMAP sync started. Fetching emails received since: {start_dt.isoformat()} (IMAP search date: {imap_date_str})...")

    collected_emails = []

    try:
        # Kết nối IMAP SSL
        context = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL(imap_server, port=993, ssl_context=context)
        mail.login(email_user, email_pass)
        
        # Chọn hộp thư đến Inbox (Read-Only)
        mail.select("INBOX", readonly=True)
        
        # Tìm các email từ ngày imap_date_str trở đi
        search_criterion = f'SINCE {imap_date_str}'
        status, data = mail.search(None, search_criterion)
        
        if status != "OK" or not data or not data[0]:
            print("No emails found since search date.")
            mail.logout()
            return

        msg_ids = data[0].split()
        print(f"Found {len(msg_ids)} potential emails on IMAP server. Filtering precise timestamp...")

        # Nhóm theo tiêu đề đã chuẩn hóa
        grouped_threads = {}

        for msg_id in msg_ids:
            # Tải toàn bộ cấu trúc email
            res_status, msg_data = mail.fetch(msg_id, '(RFC822)')
            if res_status != "OK" or not msg_data:
                continue
                
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Kiểm tra thời gian chính xác
            date_str = msg.get("Date")
            email_dt = parse_email_date(date_str)
            
            if not email_dt:
                continue
                
            # Đảm bảo datetime có timezone
            if email_dt.tzinfo is None:
                email_dt = email_dt.replace(tzinfo=timezone.utc)
                
            # Kiểm tra xem có nhận sau mốc start_dt hay không
            if email_dt < start_dt:
                continue
                
            # Đọc headers
            subject_raw = msg.get("Subject", "")
            subject = decode_mime_words(subject_raw)
            
            from_raw = msg.get("From", "")
            sender = decode_mime_words(from_raw)
            
            # Chuẩn hóa subject để nhóm luồng
            norm_subj = normalize_subject(subject)
            room_title = f"Email: {norm_subj}"
            
            # Lấy nội dung body
            body = get_email_body(msg)
            if not body:
                body = "(Email không có nội dung văn bản)"
                
            email_msg = {
                "sender": sender,
                "text": body,
                "timestamp": email_dt.isoformat()
            }
            
            if room_title not in grouped_threads:
                grouped_threads[room_title] = []
            grouped_threads[room_title].append(email_msg)

        mail.logout()

        # Tạo danh sách các phòng chat email
        for room_name, messages in grouped_threads.items():
            # Sắp xếp tin nhắn theo thời gian tăng dần
            messages.sort(key=lambda x: x["timestamp"])
            collected_emails.append({
                "room_name": room_name,
                "room_type": "email",
                "messages": messages
            })

        print(f"Successfully processed {len(collected_emails)} email threads.")

    except Exception as e:
        print(f"[ERROR] Email sync failed: {e}")
        return

    # 3. Ghi/Gộp vào chat_raw.json
    output_file = os.path.join(base_dir, "chat_raw.json")
    existing_chats = []
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                existing_chats = json.load(f)
                if not isinstance(existing_chats, list):
                    existing_chats = []
        except Exception:
            pass

    # Gộp theo room_name
    chat_map = {c.get("room_name"): c for c in existing_chats if c.get("room_name")}
    
    for new_c in collected_emails:
        rname = new_c.get("room_name")
        if rname in chat_map:
            # Tránh trùng lặp tin nhắn email
            existing_msgs = chat_map[rname].get("messages", [])
            existing_texts = {m.get("text") for m in existing_msgs}
            for m in new_c.get("messages", []):
                if m.get("text") not in existing_texts:
                    existing_msgs.append(m)
        else:
            existing_chats.append(new_c)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(existing_chats, f, ensure_ascii=False, indent=2)

    print(f"[SUCCESS] Email sync completed! Added/merged {len(collected_emails)} threads into '{output_file}'.")

if __name__ == "__main__":
    main()
