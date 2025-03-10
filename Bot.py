import logging
import sqlite3
import requests
import openai
import asyncio
from fastapi import FastAPI, Request
from bs4 import BeautifulSoup
from newspaper import Article
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, CallbackContext
import uvicorn

WEBHOOK_URL = "https://bot-cqbh.onrender.com/webhook"  # Thay bằng URL server của bạn
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
openai.api_key = OPENAI_API_KEY

# 🔹 Cấu hình FastAPI
app = FastAPI()

# 🔹 Kết nối SQLite
conn = sqlite3.connect("queries.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    query_text TEXT UNIQUE,
    response_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

# 🔹 Hàm lưu câu hỏi vào database
def save_query(user_id, query_text, response_text):
    conn = sqlite3.connect("queries.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO queries (user_id, query_text, response_text) VALUES (?, ?, ?)",
        (user_id, query_text, response_text),
    )
    conn.commit()
    conn.close()

# 🔹 Hàm kiểm tra dữ liệu đã có chưa
def check_existing_query(query_text):
    conn = sqlite3.connect("queries.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT response_text FROM queries WHERE query_text = ? ORDER BY created_at DESC LIMIT 1",
        (query_text,),
    )
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# 🔹 Hàm xử lý lệnh /help
async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = """
🤖 **Danh sách lệnh có sẵn:**
/help - Hiển thị danh sách lệnh và hướng dẫn sử dụng.
/stocksearch <câu hỏi> - Tìm kiếm thông tin chứng khoán và tóm tắt bằng AI.
/start - Bắt đầu bot, kiểm tra kết nối.

📌 **Ví dụ:**
`/stocksearch VN-Index hôm nay thế nào?`
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

# 🔹 Hàm xử lý lệnh /stocksearch
async def stock_search(update: Update, context: CallbackContext) -> None:
    if not context.args:
        await update.message.reply_text("❗ Vui lòng nhập câu hỏi về chứng khoán!")
        return

    query = " ".join(context.args)
    user_id = update.message.chat_id

    existing_response = check_existing_query(query)
    if existing_response:
        await update.message.reply_text(f"✅ **Dữ liệu đã có:**\n{existing_response}")
        return

    await update.message.reply_text("🔍 Đang tìm kiếm thông tin...")

    # 🔹 Gọi API tìm kiếm ở đây
    response_text = "🔹 Đây là dữ liệu chứng khoán tìm được."

    # Lưu vào database
    save_query(user_id, query, response_text)

    await update.message.reply_text(response_text)

# 🔹 Khởi tạo bot Telegram
bot = Bot(token=TELEGRAM_TOKEN)
app_telegram = Application.builder().token(TELEGRAM_TOKEN).build()

# 🔹 Hàm khởi tạo bot trước khi chạy webhook
async def init_bot():
    await app_telegram.initialize()
    await app_telegram.start()

# 🔹 Thêm các lệnh vào bot
app_telegram.add_handler(CommandHandler("stocksearch", stock_search))
app_telegram.add_handler(CommandHandler("help", help_command))

# 🔹 Webhook xử lý dữ liệu từ Telegram
@app.post("/webhook")
async def webhook(request: Request):
    update = Update.de_json(await request.json(), bot)

    if not app_telegram.bot:
        await init_bot()  # Đảm bảo bot được khởi tạo trước khi xử lý update

    await app_telegram.process_update(update)
    return {"status": "Webhook received"}

# 🔹 Route kiểm tra webhook hoạt động
@app.get("/webhook")
async def webhook_info():
    return {"status": "Webhook is active"}

# 🔹 Route kiểm tra bot có chạy không
@app.get("/")
async def home():
    return {"status": "Bot is running!", "webhook": WEBHOOK_URL}

# 🔹 Lệnh thiết lập webhook
async def set_webhook():
    await bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook đã được thiết lập: {WEBHOOK_URL}")

# 🔹 Chạy FastAPI với Uvicorn
if __name__ == "__main__":
    import uvicorn

    async def main():
        await set_webhook()  # Thiết lập webhook trước
        await init_bot()  # Khởi tạo bot

    loop = asyncio.get_event_loop()
    loop.create_task(main())  # Chạy bot mà không bị lỗi event loop
    uvicorn.run(app, host="0.0.0.0", port=5000)
