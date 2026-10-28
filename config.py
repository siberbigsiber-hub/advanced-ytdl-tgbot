import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 10000))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN غير موجود. أضفه إلى متغيرات البيئة في Render أو خادمك.")
