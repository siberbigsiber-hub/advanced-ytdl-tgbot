import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))
DEFAULT_COOKIES_PATH = os.path.abspath(os.path.join(os.getcwd(), "cookies.txt"))
YT_COOKIES_FILE = os.getenv("YT_COOKIES_FILE", DEFAULT_COOKIES_PATH)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN غير موجود. أضفه في Render أو الخادم كمتغير بيئة.")

if YT_COOKIES_FILE and not os.path.exists(YT_COOKIES_FILE):
    print(f"[INFO] ملف cookies غير موجود: {YT_COOKIES_FILE}. سيتم انتظار تحديثه من Mini App.")
