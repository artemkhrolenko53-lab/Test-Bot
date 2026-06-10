import os
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import threading

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("❌ BOT_TOKEN не найден!")

# ВАШ URL (замените после деплоя)
RENDER_URL = "https://test-bot.onrender.com"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

DB_PATH = "/tmp/data.db"

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER, chat_id TEXT, name TEXT, messages INTEGER DEFAULT 0)')
    conn.commit()
    conn.close()

init_db()

# ========== HTML ==========
HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Helix Bot</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { font-family: system-ui; padding: 20px; text-align: center; background: #0a0a0f; color: white; }
        .card { background: #1a1a24; border-radius: 16px; padding: 20px; margin: 10px 0; }
        .stat { font-size: 48px; font-weight: bold; color: #667eea; }
        button { background: #667eea; color: white; border: none; padding: 12px 24px; border-radius: 12px; margin: 10px; cursor: pointer; }
    </style>
</head>
<body>
    <h1>✅ Helix Bot</h1>
    <div class="card">
        <div>Всего сообщений</div>
        <div class="stat" id="total">0</div>
    </div>
    <button onclick="refresh()">🔄 Обновить</button>
    <button onclick="window.Telegram.WebApp.close()">❌ Закрыть</button>
    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();
        async function refresh() {
            let res = await fetch('/api/stats');
            let data = await res.json();
            document.getElementById('total').innerText = data.total || 0;
        }
        refresh();
    </script>
</body>
</html>
"""

# ========== API ==========
@app.route('/')
def index():
    return HTML

@app.route('/api/stats')
def stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT SUM(messages) FROM users')
    total = c.fetchone()[0] or 0
    conn.close()
    return jsonify({'total': total})

# ========== КОМАНДЫ БОТА ==========
@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📱 Открыть панель", web_app=WebAppInfo(RENDER_URL)))
    bot.send_message(message.chat.id, "✅ Бот работает! Нажми кнопку ниже:", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def count(m):
    if m.chat.type in ["group", "supergroup"] and not m.from_user.is_bot:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO users (user_id, chat_id, name, messages) VALUES (?, ?, ?, 1) ON CONFLICT(user_id, chat_id) DO UPDATE SET messages = messages + 1',
                  (m.from_user.id, str(m.chat.id), m.from_user.first_name))
        conn.commit()
        conn.close()

# ========== ЗАПУСК ==========
def run_flask():
    app.run(host='0.0.0.0', port=8080, debug=False)

if __name__ == '__main__':
    # Удаляем webhook при старте
    try:
        bot.remove_webhook()
        print("✅ Webhook удалён")
    except:
        pass
    
    # Запускаем Flask в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("🚀 Бот запущен (polling mode)!")
    # Запускаем polling
    bot.infinity_polling(skip_pending=True)
