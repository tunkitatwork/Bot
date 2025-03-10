import logging
import os
import sqlite3
import requests
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import asyncio
from fastapi import FastAPI, Request
from bs4 import BeautifulSoup
from newspaper import Article
from telegram import Update, ForceReply
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackContext, ContextTypes, filters
)
import googlesearch

# 🔹 Cấu hình bot
TOKEN = "7921895980:AAF8DW0r6xqTBFlIx-Lh3DcWueFssbUmjfc"
WEBHOOK_URL = f"https://bot-cqbh.onrender.com"


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


# 🔹 Hàm xử lý các lệnh
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gửi tin nhắn chào mừng và hướng dẫn."""
    await update.message.reply_text(
        "Chào mừng! Tôi là bot hỗ trợ cảnh báo tín hiệu mua/bán tiền mã hóa.\n"
        "Dưới đây là các lệnh bạn có thể sử dụng:\n"
        "Gõ /chart <mã giao dịch> để xem biểu đồ kỹ thuật (ví dụ: /chart BTC/USDT).\n"
        "Gõ /top để xem top 10 cặp giao dịch tăng, giảm mạnh nhất 24 giờ qua.\n"
        "Gõ /signal <mã giao dịch> để xem lịch sử tín hiệu mua bán trong 7 ngày qua.\n"
        "Gõ /smarttrade <mã giao dịch> để xem thông tin và tín hiệu mua bán mới nhất.\n"
        "Gõ /list để xem top 10 cặp giao dịch có tín hiệu mua bán gần đây.\n"
        "Gõ /list10 để xem tín hiệu mua bán gần đây của 10 cặp giao dịch có vốn hóa lớn nhất thị trường.\n"
        "Gõ /info để xem thông tin đồng coin.\n"
        "Gõ /heatmap để xem heatmap của 100 đồng coin.\n"
        "Gõ /sentiment để xem sentiment.\n"
        "Gõ /desc để xem mô tả đồng coin.\n"
        "Gõ /trending để xem top 15 trend coin."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
🤖 **Danh sách lệnh có sẵn:**
/help - Hiển thị danh sách lệnh và hướng dẫn sử dụng.
/stocksearch <câu hỏi> - Tìm kiếm thông tin chứng khoán và tóm tắt bằng AI.
/start - Bắt đầu bot, kiểm tra kết nối.

📌 **Ví dụ:**
`/stocksearch VN-Index hôm nay thế nào?`
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

def search_google(query):
    try:
        search_results = []
        for url in googlesearch.search(query + " site:cafef.vn OR site:vietstock.vn", num_results=3):
            article = Article(url)
            article.download()
            article.parse()
            search_results.append((article.title, url, article.text[:2000]))  # Giới hạn nội dung 2000 ký tự
        return search_results
    except Exception:
        return []

def summarize_with_mistral(content):
    model_name = "mistralai/Mistral-7B-Instruct"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)

    generator = pipeline("text-generation", model=model, tokenizer=tokenizer)
    summary = generator(f"Tóm tắt thông tin tài chính sau: {content}", max_length=200, do_sample=True)

    return summary[0]["generated_text"]

async def stock_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Hiển thị khung nhập để người dùng nhập câu hỏi sau khi gõ lệnh."""
    
    await update.message.reply_text(
        "🔍 Vui lòng nhập câu hỏi về chứng khoán:",
        reply_markup=ForceReply(selective=True)  # Tạo khung nhập câu hỏi
    )

async def handle_stock_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý câu hỏi sau khi người dùng nhập vào."""
    query = update.message.text.strip()
    user_id = update.message.chat_id

    if not query:
        await update.message.reply_text("❗ Bạn chưa nhập câu hỏi!")
        return

    await update.message.reply_text(f"🔍 Đang tìm kiếm thông tin về: {query}...")

    # 🔹 Gọi API tìm kiếm Google
    search_results = search_google(query)
    if not search_results:
        await update.message.reply_text("⚠ Không tìm thấy thông tin phù hợp!")
        return

    # 🔹 Lấy nội dung từ kết quả tìm kiếm đầu tiên
    title, url, content = search_results[0]

    # 🔹 Dùng GPT để tóm tắt và tổng hợp thông tin
    summary = summarize_with_mistral(content)

    response_text = f"📌 **{title}**\n🔗 {url}\n📝 **Tóm tắt:** {summary}"

    # 🔹 Gửi kết quả cho người dùng
    await update.message.reply_text(response_text)


async def set_webhook(application: Application):
    """Thiết lập Webhook."""
    await application.bot.set_webhook(WEBHOOK_URL)

def main():
    # Lấy cổng từ biến môi trường hoặc sử dụng cổng mặc định
    port = int(os.getenv("PORT", 8080))
    print(f"Đang sử dụng cổng: {port}")  # Log kiểm tra cổng

    # Khởi tạo ứng dụng Telegram bot
    application = Application.builder().token(TOKEN).build()

    # Đăng ký các handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stocksearch", stock_search))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_stock_query))
    application.add_handler(CommandHandler("help", help_command))


    # Chạy webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    main()
