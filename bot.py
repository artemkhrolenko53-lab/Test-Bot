@bot.message_handler(func=lambda m: True)
def debug_all_messages(message):
    print(f"🔥 ВСЕ СООБЩЕНИЯ: chat_id={message.chat.id}, user={message.from_user.id}, text={message.text}")
    bot.send_message(message.chat.id, f"✅ Бот видит сообщение: {message.text[:50]}")
