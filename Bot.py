import logging
import os
import sqlite3
import requests
import openai
import asyncio
from fastapi import FastAPI, Request
from bs4 import BeautifulSoup
from newspaper import Article
from telegram import Bot, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, CallbackContext
)
import uvicorn

# 🔹 Cấu hình bot
TOKEN = "7921895980:AAF8DW0r6xqTBFlIx-Lh3DcWueFssbUmjfc"
WEBHOOK_URL = f"https://bot-cqbh.onrender.com"
OPENAI_API_KEY = "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"
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

# 🔹 Hàm xử lý các lệnh
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("🤖 Chào mừng bạn đến với bot!")

async def chart(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("📊 Hiển thị biểu đồ...")

async def signal(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("📈 Tín hiệu giao dịch...")

async def top(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("🔝 Top cổ phiếu hot...")

async def list_signals(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("📜 Danh sách tín hiệu...")

async def current_price(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("💰 Giá hiện tại...")

async def info(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("ℹ️ Thông tin thị trường...")

async def heatmap(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("🌡️ Heatmap thị trường...")

async def desc(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("📖 Mô tả chi tiết...")

async def sentiment(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("📊 Phân tích cảm xúc...")

async def trending(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("🔥 Xu hướng thị trường...")

async def list10(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("🔟 Danh sách 10 cổ phiếu hàng đầu...")

async def button(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("🔘 Bạn đã nhấn nút!")

# 🔹 Khởi tạo bot Telegram
bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()

# 🔹 Hàm khởi tạo bot trước khi chạy webhook
async def init_bot():
    await application.initialize()
    await application.start()

# 🔹 Đăng ký handler
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("chart", chart))
application.add_handler(CommandHandler("signal", signal))
application.add_handler(CommandHandler("top", top))
application.add_handler(CommandHandler("list", list_signals))
application.add_handler(CommandHandler("smarttrade", current_price))
application.add_handler(CommandHandler("info", info))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(CommandHandler("heatmap", heatmap))
application.add_handler(CommandHandler("desc", desc))
application.add_handler(CommandHandler("sentiment", sentiment))
application.add_handler(CommandHandler("trending", trending))
application.add_handler(CommandHandler("list10", list10))

# 🔹 Webhook xử lý dữ liệu từ Telegram
@app.post("/webhook")
async def webhook(request: Request):
    update = Update.de_json(await request.json(), bot)

    # Kiểm tra nếu bot chưa được khởi tạo, thì khởi tạo trước
    if not application._initialized:
        await init_bot()

    await application.process_update(update)
    return {"status": "Webhook received"}

# 🔹 Route kiểm tra bot có chạy không
@app.get("/", methods=["GET", "HEAD"])
async def home():
    return {"status": "Bot is running!", "webhook": WEBHOOK_URL}

# 🔹 Lệnh thiết lập webhook
async def set_webhook():
    await bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook đã được thiết lập: {WEBHOOK_URL}")

# 🔹 Chạy bot bằng webhook
def main():
    # Lấy cổng từ biến môi trường hoặc sử dụng cổng mặc định
    port = int(os.getenv("PORT", 8080))
    print(f"🚀 Đang sử dụng cổng: {port}")  # Log kiểm tra cổng

    async def start_services():
        await init_bot()
        await set_webhook()
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=WEBHOOK_URL
        )

    loop = asyncio.get_event_loop()
    loop.create_task(start_services())  # Chạy bot Telegram song song với webhook

    # Chạy FastAPI với Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)

# 🔹 Chạy `main()` khi script được khởi động
if __name__ == "__main__":
    main()
