import logging
import sqlite3
import requests
import openai
from bs4 import BeautifulSoup
from newspaper import Article
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import asyncio

WEBHOOK_URL = "https://your-server.com/webhook"  # Thay bằng URL server của bạn

# 🔹 Cấu hình bot Telegram
TELEGRAM_TOKEN = "7921895980:AAF8DW0r6xqTBFlIx-Lh3DcWueFssbUmjfc"

# 🔹 Cấu hình OpenAI API (Dùng GPT để tóm tắt)
OPENAI_API_KEY = "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"
openai.api_key = OPENAI_API_KEY

# 🔹 Cấu hình logging
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# 🔹 Kết nối SQLite
conn = sqlite3.connect("queries.db", check_same_thread=False)
cursor = conn.cursor()

# Tạo bảng nếu chưa có
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

# 🔹 Hàm lưu câu hỏi và phản hồi vào SQLite
def save_query(user_id, query_text, response_text):
    cursor.execute(
        "INSERT OR IGNORE INTO queries (user_id, query_text, response_text) VALUES (?, ?, ?)",
        (user_id, query_text, response_text),
    )
    conn.commit()

# 🔹 Hàm kiểm tra câu hỏi đã tồn tại chưa
def check_existing_query(query_text):
    cursor.execute(
        "SELECT response_text FROM queries WHERE query_text = ? ORDER BY created_at DESC LIMIT 1",
        (query_text,),
    )
    result = cursor.fetchone()
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

# 🔹 Hàm xử lý lệnh /stocksearch
async def stock_search(update: Update, context: CallbackContext) -> None:
    print(f"📩 Nhận lệnh từ {update.message.chat.username}: {update.message.text}")

    if not context.args:
        await update.message.reply_text("❗ Vui lòng nhập câu hỏi về chứng khoán!")
        return

    query = " ".join(context.args)
    user_id = update.message.chat_id

    # Kiểm tra xem câu hỏi đã có trong database chưa
    existing_response = check_existing_query(query)
    if existing_response:
        print("✅ Trả lời từ database.")
        await update.message.reply_text(f"✅ **Dữ liệu đã có:**\n{existing_response}")
        return

    print("🔍 Đang tìm kiếm thông tin trên Google...")
    await update.message.reply_text("🔍 Đang tìm kiếm thông tin...")

    # Tìm kiếm Google
    search_results = search_google(query)
    if not search_results:
        await update.message.reply_text("⚠ Không tìm thấy thông tin phù hợp.")
        return

    title, url = search_results[0]
    print(f"📌 Lấy nội dung từ: {url}")

    content = extract_content(url)
    
    if content:
        await update.message.reply_text(f"📌 **Bài viết:** {title}\n🔗 {url}\n⏳ Đang tóm tắt thông tin...")
        summary = summarize_text(content)
        response_text = f"📝 **Tóm tắt:**\n{summary}"

        # Lưu vào database
        save_query(user_id, query, response_text)
        print("✅ Đã lưu vào database.")

        await update.message.reply_text(response_text)
    else:
        await update.message.reply_text(f"Không thể lấy nội dung từ {url}")


# 🔹 Chạy bot Telegram
async def main():
    print("🚀 Đang khởi động bot Telegram...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    print("✅ Thêm command handler...")
    app.add_handler(CommandHandler("stocksearch", stock_search))

    print("🤖 Bot đang chạy, chờ tin nhắn...")
    await app.run_polling()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    
    if loop.is_running():
        print("⚠ Event loop đã chạy, dùng create_task() thay vì run().")
        loop.create_task(main())  # Dùng create_task() nếu loop đã chạy
    else:
        loop.run_until_complete(main())  # Chạy bình thường nếu loop chưa chạy
