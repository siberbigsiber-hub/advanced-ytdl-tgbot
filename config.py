import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))
YT_COOKIES_FILE = os.getenv("YT_COOKIES_FILE")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN غير موجود. أضفه إلى متغيرات البيئة في Render أو خادمك.")

if YT_COOKIES_FILE and not os.path.exists(YT_COOKIES_FILE):
    raise FileNotFoundError(f"ملف cookies غير موجود: {YT_COOKIES_FILE}")
