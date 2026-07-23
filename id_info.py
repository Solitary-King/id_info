import io
import os
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestChat,
    KeyboardButtonRequestUsers,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


# --- Render-এর জন্য Dummy HTTP Server ---
class HealthCheckHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.send_header("Content-type", "text/plain")
    self.end_headers()
    self.wfile.write(b"Bot is running alive!")


def run_dummy_server():
  # Render স্বয়ংক্রিয়ভাবে PORT নামক Environment Variable সেট করে দেয়
  port = int(os.environ.get("PORT", 8080))
  server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
  server.serve_forever()


# ----------------------------------------------------
# ১. আপনার তথ্যাদি এখানে দিন
BOT_TOKEN = "8846566321:AAFGCEpH2-yzYki79s1WIgilSwetxQG5Gy8"
ADMIN_ID = 6535070545  # <--- আপনার নিজস্ব টেলিগ্রাম ইউজার আইডি
# ----------------------------------------------------


# --- ডাটাবেজ ফাংশনসমূহ ---
def init_db():
  conn = sqlite3.connect("bot_data.db")
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
  conn = sqlite3.connect("bot_data.db")
  cursor = conn.cursor()
  cursor.execute(
      """
        INSERT OR REPLACE INTO users (user_id, first_name, username) 
        VALUES (?, ?, ?)
    """,
      (user_id, first_name, username),
  )
  conn.commit()
  conn.close()


def get_total_users():
  conn = sqlite3.connect("bot_data.db")
  cursor = conn.cursor()
  cursor.execute("SELECT COUNT(*) FROM users")
  count = cursor.fetchone()[0]
  conn.close()
  return count


def get_all_users_details():
  conn = sqlite3.connect("bot_data.db")
  cursor = conn.cursor()
  cursor.execute("SELECT user_id, first_name, username FROM users")
  users = cursor.fetchall()
  conn.close()
  return users


# --- এডমিন প্যানেল কিবোর্ড ---
def get_admin_keyboard():
  return InlineKeyboardMarkup([
      [InlineKeyboardButton("📊 Refresh Stats", callback_data="refresh_stats")],
      [
          InlineKeyboardButton(
              "📁 Export All Users Data", callback_data="export_users"
          )
      ],
      [
          InlineKeyboardButton(
              "📢 Broadcast Message", callback_data="broadcast_info"
          )
      ],
  ])


async def show_admin_panel(update: Update):
  total_users = get_total_users()

  admin_text = (
      f"⚙️ <b>-- Admin Control Panel --</b> ⚙️\n\n"
      f"👥 <b>Total Registered Users:</b> <code>{total_users}</code>\n"
      f"⚡ <b>System Status:</b> Online ✅\n\n"
      f"নিচের মেনু থেকে আপনার কাঙ্ক্ষিত অপশন সিলেক্ট করুন:"
  )

  if update.callback_query:
    await update.callback_query.message.reply_html(
        admin_text, reply_markup=get_admin_keyboard()
    )
  else:
    await update.message.reply_html(
        admin_text, reply_markup=get_admin_keyboard()
    )


# --- হ্যান্ডলারসমূহ ---


# /start কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user = update.effective_user
  add_user(user.id, user.first_name, user.username)

  username = f"@{user.username}" if user.username else "কোনো ইউজারনেম নেই"
  full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

  welcome_text = (
      f"{username}\n\n"
      f"👋 Welcome!\n"
      f"<b>ID:</b> <code>{user.id}</code>\n"
      f"<b>Name:</b> {full_name}"
  )

  # মূল ৪টি বাটন
  keyboard = [
      [
          KeyboardButton(
              text="User",
              request_users=KeyboardButtonRequestUsers(
                  request_id=1, user_is_bot=False
              ),
          ),
          KeyboardButton(
              text="Channel",
              request_chat=KeyboardButtonRequestChat(
                  request_id=2, chat_is_channel=True
              ),
          ),
      ],
      [
          KeyboardButton(
              text="Group",
              request_chat=KeyboardButtonRequestChat(
                  request_id=3, chat_is_channel=False
              ),
          ),
          KeyboardButton(
              text="Bot",
              request_users=KeyboardButtonRequestUsers(
                  request_id=4, user_is_bot=True
              ),
          ),
      ],
  ]

  # শুধুমাত্র এডমিন হলে কিবোর্ডে এডমিন বাটন যোগ হবে
  if user.id == ADMIN_ID:
    keyboard.append([KeyboardButton(text="👑 Admin Panel")])

  reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
  await update.message.reply_html(welcome_text, reply_markup=reply_markup)


# টেক্সট মেসেজ হ্যান্ডলার
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
  user_id = update.effective_user.id
  text = update.message.text

  if text == "👑 Admin Panel" and user_id == ADMIN_ID:
    await show_admin_panel(update)


# ইনলাইন বাটন হ্যান্ডলার
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()

  if query.from_user.id != ADMIN_ID:
    return

  # ১. রিফ্রেশ
  if query.data == "refresh_stats":
    total_users = get_total_users()
    admin_text = (
        f"⚙️ <b>-- Admin Control Panel --</b> ⚙️\n\n"
        f"👥 <b>Total Registered Users:</b> <code>{total_users}</code>\n"
        f"⚡ <b>System Status:</b> Online ✅"
    )
    await query.edit_message_text(
        admin_text, parse_mode="HTML", reply_markup=get_admin_keyboard()
    )

  # ২. ডাটা ফাইল আকারে এক্সপোর্ট করা
  elif query.data == "export_users":
    users = get_all_users_details()
    if not users:
      await query.message.reply_text("❌ কোনো ডাটা নেই।")
      return

    file_content = "ID | Name | Username\n" + "=" * 30 + "\n"
    for u_id, name, uname in users:
      file_content += f"{u_id} | {name} | @{uname if uname else 'None'}\n"

    document = io.BytesIO(file_content.encode("utf-8"))
    document.name = "users_list.txt"

    await query.message.reply_document(
        document=document, caption="📄 আপনার বটের সকল ইউজারের ডাটাবেজ ফাইল।"
    )

  # ৩. ব্রডকাস্ট মেসেজ নির্দেশিকা
  elif query.data == "broadcast_info":
    await query.message.reply_html(
        "📢 <b>সবাইকে মেসেজ পাঠাতে:</b>\n"
        "কমান্ড লিখুন: <code>/send আপনার বার্তাটি লিখুন</code>\n\n"
        "উদাহরণ: <code>/send আমাদের বটে নতুন আপডেট আনা হয়েছে!</code>"
    )


# /send ব্রডকাস্ট কমান্ড
async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
  if update.effective_user.id != ADMIN_ID:
    return

  msg_to_send = " ".join(context.args)
  if not msg_to_send:
    await update.message.reply_text(
        "⚠️ অনুগ্রহ করে মেসেজের লেখাটি লিখুন। যেমন: `/send Hello`",
        parse_mode="Markdown",
    )
    return

  users = get_all_users_details()
  success = 0
  failed = 0

  status_msg = await update.message.reply_text("📢 ব্রডকাস্টিং শুরু হচ্ছে...")

  for u_id, _, _ in users:
    try:
      await context.bot.send_message(chat_id=u_id, text=msg_to_send)
      success += 1
    except Exception:
      failed += 1

  await status_msg.edit_text(
      f"✅ <b>ব্রডকাস্ট সম্পন্ন হয়েছে!</b>\n\n"
      f"<b>Sent:</b> {success}\n"
      f"<b>Failed/Blocked:</b> {failed}",
      parse_mode="HTML",
  )


# শেয়ার সংক্রান্ত হ্যান্ডলার
async def handle_users_shared(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  users_shared = update.message.users_shared
  for shared_user in users_shared.users:
    await update.message.reply_html(
        f"<b>ID:</b> <code>{shared_user.user_id}</code>"
    )


async def handle_chat_shared(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  chat_shared = update.message.chat_shared
  await update.message.reply_html(
      f"<b>ID:</b> <code>{chat_shared.chat_id}</code>"
  )


# --- মূল রানার ---
if __name__ == "__main__":
  # Render-এর জন্য ডামি এইচটিটিপি সার্ভার আলাদা থ্রেডে চালু করা হচ্ছে
  server_thread = threading.Thread(target=run_dummy_server, daemon=True)
  server_thread.start()

  init_db()
  app = ApplicationBuilder().token(BOT_TOKEN).build()

  # হ্যান্ডলার রেজিস্টার
  app.add_handler(CommandHandler("start", start))
  app.add_handler(CommandHandler("send", broadcast_send))

  app.add_handler(CallbackQueryHandler(button_click))

  app.add_handler(
      MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages)
  )
  app.add_handler(
      MessageHandler(filters.StatusUpdate.USERS_SHARED, handle_users_shared)
  )
  app.add_handler(
      MessageHandler(filters.StatusUpdate.CHAT_SHARED, handle_chat_shared)
  )

  print("বট সফলভাবে চালু হয়েছে...")
  app.run_polling()
