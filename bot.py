import os
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import threading
from datetime import datetime

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("❌ BOT_TOKEN не найден!")

# ЗАМЕНИТЕ НА ВАШ URL (после деплоя)
RENDER_URL = "https://test-bot.onrender.com"

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

DB_PATH = "/tmp/data.db"

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER, chat_id TEXT, name TEXT, messages INTEGER DEFAULT 0, warnings INTEGER DEFAULT 0, muted INTEGER DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, user_name TEXT, action TEXT, message TEXT, created_at TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS binding (chat_id TEXT PRIMARY KEY, chat_title TEXT)')
    conn.commit()
    conn.close()

init_db()

# ========== HTML (МИНИ-АПП) ==========
HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Helix Manager</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: var(--tg-theme-bg-color, #f5f5f7);
            color: var(--tg-theme-text-color, #1c1c1e);
            padding: 20px;
            padding-bottom: 80px;
        }
        @media (prefers-color-scheme: dark) {
            body { background: #0a0a0a; color: #ffffff; }
        }
        .header { margin-bottom: 24px; }
        .header h1 {
            font-size: 28px;
            font-weight: 600;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header p { font-size: 14px; color: #666; margin-top: 4px; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 24px;
        }
        .stat-card {
            background: var(--tg-theme-secondary-bg-color, #ffffff);
            border-radius: 16px;
            padding: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border: 1px solid rgba(0,0,0,0.05);
        }
        .stat-value { font-size: 32px; font-weight: 700; color: #667eea; }
        .stat-label { font-size: 13px; color: #666; margin-top: 6px; }
        .section {
            background: var(--tg-theme-secondary-bg-color, #ffffff);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 16px;
            border: 1px solid rgba(0,0,0,0.05);
        }
        .section-title { font-size: 17px; font-weight: 600; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid rgba(0,0,0,0.1); }
        .user-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid rgba(0,0,0,0.05);
            cursor: pointer;
        }
        .user-name { font-weight: 500; font-size: 16px; }
        .user-count { font-size: 14px; color: #667eea; font-weight: 500; }
        .log-item { padding: 10px 0; border-bottom: 1px solid rgba(0,0,0,0.05); font-size: 13px; }
        .log-time { font-size: 11px; color: #888; margin-bottom: 4px; }
        .input-field {
            width: 100%;
            padding: 14px;
            background: var(--tg-theme-secondary-bg-color, #f9f9f9);
            border: 1px solid rgba(0,0,0,0.1);
            border-radius: 12px;
            font-size: 16px;
            margin-bottom: 12px;
            outline: none;
        }
        .input-field:focus { border-color: #667eea; }
        .btn {
            width: 100%;
            padding: 14px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
        }
        .bottom-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: var(--tg-theme-secondary-bg-color, rgba(255,255,255,0.95));
            backdrop-filter: blur(20px);
            display: flex;
            justify-content: space-around;
            padding: 12px 20px 25px;
            border-top: 0.5px solid rgba(0,0,0,0.1);
        }
        .nav-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            opacity: 0.5;
        }
        .nav-item.active { opacity: 1; }
        .nav-icon { font-size: 22px; }
        .nav-label { font-size: 11px; font-weight: 500; }
        .page { display: none; }
        .page.active { display: block; }
        .action-menu {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: var(--tg-theme-secondary-bg-color, #ffffff);
            border-radius: 20px 20px 0 0;
            padding: 20px;
            transform: translateY(100%);
            transition: transform 0.3s ease;
            z-index: 1000;
        }
        .action-menu.open { transform: translateY(0); }
        .menu-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.4);
            backdrop-filter: blur(4px);
            z-index: 999;
            display: none;
        }
        .menu-overlay.open { display: block; }
        .action-title { font-size: 18px; font-weight: 600; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid rgba(0,0,0,0.1); }
        .action-btn { width: 100%; padding: 14px; border: none; border-radius: 12px; font-size: 16px; font-weight: 500; margin-bottom: 10px; cursor: pointer; }
        .action-mute { background: #ff3b30; color: white; }
        .action-unmute { background: #34c759; color: white; }
        .action-warn { background: #ff9500; color: white; }
        .action-cancel { background: #e5e5ea; color: #1c1c1e; }
        .refresh-btn {
            position: fixed;
            bottom: 80px;
            right: 16px;
            width: 48px;
            height: 48px;
            background: #667eea;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 22px;
            z-index: 90;
            border: none;
        }
        .loading { text-align: center; padding: 40px; color: #888; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Helix Manager</h1>
        <p>Управление чатом</p>
    </div>
    <div class="bottom-nav">
        <div class="nav-item active" data-page="stats"><div class="nav-icon">📊</div><div class="nav-label">Статистика</div></div>
        <div class="nav-item" data-page="users"><div class="nav-icon">👥</div><div class="nav-label">Участники</div></div>
        <div class="nav-item" data-page="logs"><div class="nav-icon">📋</div><div class="nav-label">Логи</div></div>
        <div class="nav-item" data-page="bind"><div class="nav-icon">🔗</div><div class="nav-label">Привязка</div></div>
    </div>
    <div id="statsPage" class="page active">
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value" id="totalUsers">0</div><div class="stat-label">участников</div></div>
            <div class="stat-card"><div class="stat-value" id="totalMsgs">0</div><div class="stat-label">сообщений</div></div>
        </div>
        <div class="section"><div class="section-title">🏆 Топ участников</div><div id="topList">Загрузка...</div></div>
    </div>
    <div id="usersPage" class="page"><div class="section"><div class="section-title">👥 Список участников</div><div id="usersList">Загрузка...</div></div></div>
    <div id="logsPage" class="page"><div class="section"><div class="section-title">📋 Логи действий</div><div id="logsList">Загрузка...</div></div></div>
    <div id="bindPage" class="page">
        <div class="section"><div class="section-title">🔗 Привязка чата</div>
        <input type="text" id="chatIdInput" class="input-field" placeholder="ID чата">
        <input type="text" id="chatTitleInput" class="input-field" placeholder="Название (необязательно)">
        <button class="btn" onclick="bindChat()">Привязать</button>
        <div id="bindStatus" style="margin-top: 12px; font-size: 13px; text-align: center;"></div></div>
        <div class="section"><div class="section-title">💡 Команды</div>
        <div style="font-size: 13px; line-height: 1.8;"><code>/start</code> — приветствие<br><code>/id</code> — ID чата<br><code>/bind</code> — привязать чат<br><code>/top</code> — топ участников</div></div>
    </div>
    <button class="refresh-btn" onclick="refreshAll()">↻</button>
    <div class="menu-overlay" id="menuOverlay" onclick="closeMenu()"></div>
    <div class="action-menu" id="actionMenu">
        <div class="action-title" id="actionUserName"></div>
        <button class="action-btn action-mute" onclick="doAction('mute')">🔇 Замутить</button>
        <button class="action-btn action-unmute" onclick="doAction('unmute')">🎤 Снять мут</button>
        <button class="action-btn action-warn" onclick="doAction('warn')">⚠️ Предупреждение</button>
        <button class="action-btn action-cancel" onclick="closeMenu()">Отмена</button>
    </div>
    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();
        let selectedUserId = null;
        async function loadStats() {
            try {
                let res = await fetch('/api/stats');
                let data = await res.json();
                document.getElementById('totalUsers').innerText = data.total_users || 0;
                document.getElementById('totalMsgs').innerText = data.total_messages || 0;
                let html = '';
                if (data.top && data.top.length) {
                    data.top.forEach((u, i) => { html += `<div class="user-row"><span class="user-name">${i+1}. ${u.name}</span><span class="user-count">${u.count}</span></div>`; });
                } else { html = '<div class="loading">Нет данных</div>'; }
                document.getElementById('topList').innerHTML = html;
            } catch(e) { console.error(e); }
        }
        async function loadUsers() {
            try {
                let res = await fetch('/api/users');
                let data = await res.json();
                let html = '';
                if (data.users && data.users.length) {
                    data.users.forEach(u => {
                        let badge = '';
                        if (u.warnings > 0) badge = `<span style="color:#ff9500; margin-left:8px;">⚠️${u.warnings}</span>`;
                        if (u.muted) badge = `<span style="color:#ff3b30; margin-left:8px;">🔇</span>`;
                        html += `<div class="user-row" onclick="openMenu(${u.id}, '${u.name.replace(/'/g, "\\'")}')"><span class="user-name">${u.name} ${badge}</span><span class="user-count">📝 ${u.messages}</span></div>`;
                    });
                } else { html = '<div class="loading">Нет участников</div>'; }
                document.getElementById('usersList').innerHTML = html;
            } catch(e) { console.error(e); }
        }
        async function loadLogs() {
            try {
                let res = await fetch('/api/logs');
                let data = await res.json();
                let html = '';
                if (data.logs && data.logs.length) {
                    data.logs.forEach(l => { html += `<div class="log-item"><div class="log-time">${l.created_at}</div><div><strong>${l.user_name}</strong> ${l.message}</div></div>`; });
                } else { html = '<div class="loading">Нет действий</div>'; }
                document.getElementById('logsList').innerHTML = html;
            } catch(e) { console.error(e); }
        }
        function openMenu(userId, userName) {
            selectedUserId = userId;
            document.getElementById('actionUserName').innerText = userName;
            document.getElementById('actionMenu').classList.add('open');
            document.getElementById('menuOverlay').classList.add('open');
            tg.HapticFeedback?.impactOccurred?.('light');
        }
        function closeMenu() {
            document.getElementById('actionMenu').classList.remove('open');
            document.getElementById('menuOverlay').classList.remove('open');
            selectedUserId = null;
        }
        async function doAction(action) {
            closeMenu();
            tg.showAlert(`Выполняется...`);
            try {
                let res = await fetch('/api/action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({user_id: selectedUserId, action: action}) });
                let data = await res.json();
                tg.showAlert(data.message);
                loadUsers(); loadStats(); loadLogs();
            } catch(e) { tg.showAlert('Ошибка: ' + e.message); }
        }
        async function bindChat() {
            let chatId = document.getElementById('chatIdInput').value.trim();
            let chatTitle = document.getElementById('chatTitleInput').value.trim() || `Чат ${chatId}`;
            if (!chatId) { tg.showAlert('Введите ID чата'); return; }
            let statusDiv = document.getElementById('bindStatus');
            statusDiv.innerHTML = '⏳ Привязка...';
            try {
                let res = await fetch('/api/bind', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({chatId: chatId, chatTitle: chatTitle}) });
                let data = await res.json();
                if (data.ok) { statusDiv.innerHTML = '✅ ' + data.message; tg.showAlert('Чат привязан!'); loadStats(); }
                else { statusDiv.innerHTML = '❌ ' + data.message; }
            } catch(e) { statusDiv.innerHTML = '❌ Ошибка: ' + e.message; }
        }
        function refreshAll() { loadStats(); loadUsers(); loadLogs(); tg.showAlert('Обновлено'); }
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                const page = item.dataset.page;
                document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
                document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
                item.classList.add('active');
                document.getElementById(page + 'Page').classList.add('active');
                if (page === 'stats') loadStats();
                if (page === 'users') loadUsers();
                if (page === 'logs') loadLogs();
            });
        });
        loadStats();
    </script>
</body>
</html>
"""

# ========== API ==========
@app.route('/')
def index():
    return HTML

@app.route('/api/stats')
def api_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0] or 0
    c.execute('SELECT SUM(messages) FROM users')
    total_messages = c.fetchone()[0] or 0
    c.execute('SELECT name, messages FROM users ORDER BY messages DESC LIMIT 10')
    top = [{'name': row[0] or 'Аноним', 'count': row[1]} for row in c.fetchall()]
    conn.close()
    return jsonify({'total_users': total_users, 'total_messages': total_messages, 'top': top})

@app.route('/api/users')
def api_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT user_id, name, messages, warnings, muted FROM users ORDER BY messages DESC')
    users = [{'id': row[0], 'name': row[1] or str(row[0]), 'messages': row[2], 'warnings': row[3], 'muted': row[4]} for row in c.fetchall()]
    conn.close()
    return jsonify({'users': users})

@app.route('/api/logs')
def api_logs():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT user_name, action, message, created_at FROM logs ORDER BY id DESC LIMIT 50')
    logs = [{'user_name': row[0], 'action': row[1], 'message': row[2], 'created_at': row[3][:16]} for row in c.fetchall()]
    conn.close()
    return jsonify({'logs': logs})

@app.route('/api/bind', methods=['POST'])
def api_bind():
    data = request.json
    chat_id = data.get('chatId')
    chat_title = data.get('chatTitle')
    if not chat_id:
        return jsonify({'ok': False, 'message': 'Не указан ID чата'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS binding (chat_id TEXT PRIMARY KEY, chat_title TEXT)')
    c.execute('INSERT OR REPLACE INTO binding (chat_id, chat_title) VALUES (?, ?)', (chat_id, chat_title))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'message': f'Чат "{chat_title}" привязан!'})

@app.route('/api/action', methods=['POST'])
def api_action():
    data = request.json
    user_id = data.get('user_id')
    action = data.get('action')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if action == 'warn':
        c.execute('UPDATE users SET warnings = warnings + 1 WHERE user_id = ?', (user_id,))
        c.execute('SELECT warnings FROM users WHERE user_id = ?', (user_id,))
        count = c.fetchone()[0]
        msg = f'⚠️ Предупреждение #{count}'
        c.execute('INSERT INTO logs (user_id, user_name, action, message, created_at) VALUES (?, ?, ?, ?, ?)',
                  (user_id, 'Администратор', 'warn', f'выдал предупреждение #{count}', datetime.now().isoformat()))
    elif action == 'mute':
        c.execute('UPDATE users SET muted = 1 WHERE user_id = ?', (user_id,))
        msg = '🔇 Пользователь замучен'
        c.execute('INSERT INTO logs (user_id, user_name, action, message, created_at) VALUES (?, ?, ?, ?, ?)',
                  (user_id, 'Администратор', 'mute', 'замутил пользователя', datetime.now().isoformat()))
    elif action == 'unmute':
        c.execute('UPDATE users SET muted = 0 WHERE user_id = ?', (user_id,))
        msg = '🎤 Мут снят'
        c.execute('INSERT INTO logs (user_id, user_name, action, message, created_at) VALUES (?, ?, ?, ?, ?)',
                  (user_id, 'Администратор', 'unmute', 'снял мут', datetime.now().isoformat()))
    else:
        msg = '✅ Выполнено'
    conn.commit()
    conn.close()
    return jsonify({'message': msg})

# ========== КОМАНДЫ БОТА ==========
@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📱 Открыть панель", web_app=WebAppInfo(RENDER_URL)))
    bot.send_message(
        message.chat.id,
        "⚡ **Helix Manager — твой чат под контролем!**\n\n"
        "Привет! Я бот, который поможет тебе управлять чатом.\n\n"
        "🚀 **Что я умею:**\n"
        "• Считать сообщения участников\n"
        "• Вести топ самых активных\n"
        "• Выдавать предупреждения\n"
        "• Ограничивать нарушителей (мут/бан)\n\n"
        "📌 **Быстрый старт:**\n"
        "→ Добавь меня в группу\n"
        "→ Сделай админом\n"
        "→ Напиши /id\n"
        "→ Открой панель управления\n\n"
        "🔥 Готов к работе! Нажми на кнопку ниже 👇",
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['id'])
def show_id(message):
    bot.reply_to(message, f"🆔 **ID чата:** `{message.chat.id}`", parse_mode='Markdown')

@bot.message_handler(commands=['bind'])
def bind_chat(message):
    if message.chat.type in ["group", "supergroup"]:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS binding (chat_id TEXT PRIMARY KEY, chat_title TEXT)')
        c.execute('INSERT OR REPLACE INTO binding (chat_id, chat_title) VALUES (?, ?)', 
                  (str(message.chat.id), message.chat.title))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ Чат **{message.chat.title}** привязан!", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ Команда /bind работает только в группах!")

@bot.message_handler(func=lambda m: True)
def count_messages(message):
    if message.chat.type in ["group", "supergroup"] and not message.from_user.is_bot:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO users (user_id, chat_id, name, messages) VALUES (?, ?, ?, 1) ON CONFLICT(user_id, chat_id) DO UPDATE SET messages = messages + 1',
                  (message.from_user.id, str(message.chat.id), message.from_user.first_name))
        conn.commit()
        conn.close()

# ========== ЗАПУСК ==========
def run_flask():
    app.run(host='0.0.0.0', port=8080, debug=False)

if __name__ == '__main__':
    try:
        bot.remove_webhook()
        print("✅ Webhook удалён")
    except:
        pass
    
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("🚀 Helix Manager запущен!")
    print(f"🤖 Бот: @{bot.get_me().username}")
    
    bot.infinity_polling(skip_pending=True)
