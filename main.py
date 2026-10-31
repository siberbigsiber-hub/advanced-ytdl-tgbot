import os
import threading

from server import app as flask_app
from bot_handlers import bot

PORT = int(os.getenv("PORT", 10000))


def run_bot():
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=10)
    except Exception as exc:
        print(f"[BOT ERROR] {exc}")


if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    flask_app.run(host="0.0.0.0", port=PORT, debug=False)
