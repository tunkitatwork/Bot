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

# 🔹 Cấu hình bot Telegram
TELEGRAM_TOKEN = "7921895980:AAF8DW0r6xqTBFlIx-Lh3DcWueFssbUmjfc"

# 🔹 Cấu hình OpenAI API (Dùng GPT để tóm tắt)
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

# 🔹 Hàm tìm kiếm Google
def search_google(query):
    url = f"https://www.google.com/search?q={query}+chứng+khoán"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        results = soup.select("h3")
        links = soup.select("div.yuRUbf a")
        
        search_results = []
        for i in range(min(3, len(results))):  # Lấy 3 kết quả đầu tiên
            title = results[i].text
            link = links[i]["href"]
            search_results.append((title, link))
        return search_results
    return []

# 🔹 Hàm lấy nội dung từ bài viết
def extract_content(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text[:2000]  # Giới hạn 2000 ký tự để tránh quá dài
    except Exception:
        return None

# 🔹 Hàm tóm tắt nội dung bằng AI
def summarize_text(text):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Bạn là chuyên gia tài chính, hãy tóm tắt nội dung này một cách dễ hiểu."},
            {"role": "user", "content": text}
        ],
        max_tokens=300
    )
    return response["choices"][0]["message"]["content"]

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

    # 🔹 Tìm kiếm Google
    search_results = search_google(query)
    if not search_results:
        await update.message.reply_text("⚠ Không tìm thấy thông tin phù hợp.")
        return

    title, url = search_results[0]
    content = extract_content(url)

    if content:
        await update.message.reply_text(f"📌 **Bài viết:** {title}\n🔗 {url}\n⏳ Đang tóm tắt thông tin...")
        summary = summarize_text(content)
        response_text = f"📝 **Tóm tắt:**\n{summary}"

        # Lưu vào database
        save_query(user_id, query, response_text)

        await update.message.reply_text(response_text)
    else:
        await update.message.reply_text(f"Không thể lấy nội dung từ {url}")

# 🔹 Khởi tạo bot Telegram
bot = Bot(token=TELEGRAM_TOKEN)
app_telegram = Application.builder().token(TELEGRAM_TOKEN).build()
async def init_application():
    await app_telegram.initialize()
    await app_telegram.start()

app_telegram.add_handler(CommandHandler("stocksearch", stock_search))
app_telegram.add_handler(CommandHandler("help", help_command))

# 🔹 Webhook xử lý dữ liệu từ Telegram
@app.get("/webhook")
async def webhook_info():
    return {"status": "Webhook is active"}
    
@app.post("/webhook")
async def webhook(request: Request):
    update = Update.de_json(await request.json(), bot)
    await app_telegram.process_update(update)  # ✅ Thêm await
    return {"status": "Webhook received"}


# 🔹 Lệnh thiết lập webhook (chạy 1 lần)
async def set_webhook():
    await bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook đã được thiết lập: {WEBHOOK_URL}")

@app.get("/")
async def home():
    return {"status": "Bot is running!", "webhook": WEBHOOK_URL}

# 🔹 Chạy FastAPI với uvicorn
if __name__ == "__main__":
    import uvicorn

    async def main():
        await set_webhook()  # Thiết lập webhook trước
        await init_application()  # Khởi tạo bot
        await app_telegram.run_webhook(
            listen="0.0.0.0",
            port=5000,
            url_path="webhook",
            webhook_url=WEBHOOK_URL
        )  # Chạy webhook

    asyncio.run(main())  # Chạy tất cả trong 1 event loop
    uvicorn.run(app, host="0.0.0.0", port=5000)

