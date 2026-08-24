import io
import os
import sqlite3
import requests
from flask import Flask, request

# ----------------------------------------------------
BOT_TOKEN = "8846566321:AAFkz8XWHvAIw9VmJg_Dq6Ehot2eeKj8WGQ"
ADMIN_ID = 6535070545
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
# ----------------------------------------------------

DB_PATH = "/tmp/bot_data.db" if os.environ.get("VERCEL") else "bot_data.db"
app = Flask(__name__)

# --- ডাটাবেজ ফাংশনসমূহ ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, first_name, username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, first_name, username) 
        VALUES (?, ?, ?)
    """, (user_id, first_name, username))
    conn.commit()
    conn.close()

def get_total_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_all_users_details():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, first_name, username FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

# --- টেলিগ্রাম এপিআই হেলপার ফাংশন ---
def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

def send_document(chat_id, document_bytes, filename, caption=None):
    files = {'document': (filename, document_bytes)}
    data = {'chat_id': chat_id}
    if caption:
        data['caption'] = caption
    requests.post(f"{TELEGRAM_API}/sendDocument", data=data, files=files)

def edit_message_text(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/editMessageText", json=payload)

def answer_callback_query(callback_query_id):
    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={"callback_query_id": callback_query_id})

# --- কিবোর্ডসমূহ ---
def get_main_keyboard(user_id):
    keyboard = [
        [
            {"text": "User", "request_users": {"request_id": 1, "user_is_bot": False}},
            {"text": "Channel", "request_chat": {"request_id": 2, "chat_is_channel": True}}
        ],
        [
            {"text": "Group", "request_chat": {"request_id": 3, "chat_is_channel": False}},
            {"text": "Bot", "request_users": {"request_id": 4, "user_is_bot": True}}
        ]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([{"text": "👑 Admin Panel"}])
    return {"keyboard": keyboard, "resize_keyboard": True}

def get_admin_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "📊 Refresh Stats", "callback_data": "refresh_stats"}],
            [{"text": "📁 Export All Users Data", "callback_data": "export_users"}],
            [{"text": "📢 Broadcast Message", "callback_data": "broadcast_info"}]
        ]
    }

# --- মেসেজ প্রসেসিং লজিক ---
init_db()

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        update = request.get_json(force=True)
        
        # ১. টেক্সট বা শেয়ার্ড বট/চ্যানেল মেসেজ হ্যান্ডলিং
        if "message" in update:
            message = update["message"]
            chat_id = message["chat"]["id"]
            user = message.get("from", {})
            user_id = user.get("id")
            text = message.get("text", "")

            add_user(user_id, user.get("first_name", ""), user.get("username", ""))

            # /start কমান্ড
            if text == "/start":
                username = f"@{user.get('username')}" if user.get("username") else "কোনো ইউজারনেম নেই"
                full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                welcome_text = f"{username}\n\n👋 Welcome!\n<b>ID:</b> <code>{user_id}</code>\n<b>Name:</b> {full_name}"
                send_message(chat_id, welcome_text, reply_markup=get_main_keyboard(user_id))

            # /send ব্রডকাস্ট কমান্ড
            elif text.startswith("/send") and user_id == ADMIN_ID:
                msg_to_send = text[5:].strip()
                if not msg_to_send:
                    send_message(chat_id, "⚠️ অনুগ্রহ করে মেসেজের লেখাটি লিখুন। যেমন: `/send Hello`", parse_mode="Markdown")
                else:
                    users = get_all_users_details()
                    success, failed = 0, 0
                    for u_id, _, _ in users:
                        try:
                            send_message(u_id, msg_to_send)
                            success += 1
                        except:
                            failed += 1
                    send_message(chat_id, f"✅ <b>ব্রডকাস্ট সম্পন্ন হয়েছে!</b>\n\n<b>Sent:</b> {success}\n<b>Failed/Blocked:</b> {failed}")

            # এডমিন প্যানেল বাটন
            elif text == "👑 Admin Panel" and user_id == ADMIN_ID:
                total_users = get_total_users()
                admin_text = f"⚙️ <b>-- Admin Control Panel --</b> ⚙️\n\n👥 <b>Total Registered Users:</b> <code>{total_users}</code>\n⚡ <b>System Status:</b> Online ✅\n\nনিচের মেনু থেকে আপনার কাঙ্ক্ষিত অপশন সিলেক্ট করুন:"
                send_message(chat_id, admin_text, reply_markup=get_admin_keyboard())

            # Shared Users (User / Bot)
            elif "users_shared" in message:
                shared_users = message["users_shared"].get("users", [])
                for s_user in shared_users:
                    send_message(chat_id, f"<b>ID:</b> <code>{s_user.get('user_id')}</code>")

            # Shared Chat (Channel / Group)
            elif "chat_shared" in message:
                chat_shared = message["chat_shared"]
                send_message(chat_id, f"<b>ID:</b> <code>{chat_shared.get('chat_id')}</code>")

        # ২. ইনলাইন বাটন হ্যান্ডলিং
        elif "callback_query" in update:
            cb = update["callback_query"]
            cb_id = cb["id"]
            user_id = cb["from"]["id"]
            data = cb.get("data")
            msg = cb.get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            message_id = msg.get("message_id")

            answer_callback_query(cb_id)

            if user_id == ADMIN_ID:
                if data == "refresh_stats":
                    total_users = get_total_users()
                    admin_text = f"⚙️ <b>-- Admin Control Panel --</b> ⚙️\n\n👥 <b>Total Registered Users:</b> <code>{total_users}</code>\n⚡ <b>System Status:</b> Online ✅"
                    edit_message_text(chat_id, message_id, admin_text, reply_markup=get_admin_keyboard())

                elif data == "export_users":
                    users = get_all_users_details()
                    if not users:
                        send_message(chat_id, "❌ কোনো ডাটা নেই।")
                    else:
                        file_content = "ID | Name | Username\n" + "="*30 + "\n"
                        for u_id, name, uname in users:
                            file_content += f"{u_id} | {name} | @{uname if uname else 'None'}\n"
                        send_document(chat_id, file_content.encode('utf-8'), "users_list.txt", caption="📄 আপনার বটের সকল ইউজারের ডাটাবেজ ফাইল।")

                elif data == "broadcast_info":
                    send_message(chat_id, "📢 <b>সবাইকে মেসেজ পাঠাতে:</b>\nকমান্ড লিখুন: <code>/send আপনার বার্তাটি লিখুন</code>\n\nউদাহরণ: <code>/send আমাদের বটে নতুন আপডেট আনা হয়েছে!</code>")

        return "OK", 200
    return "Bot is running on Vercel via Webhook!", 200
