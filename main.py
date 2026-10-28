import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# جلب التوكن بأمان من متغير البيئة
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN غير موجود. أضفه في متغيرات البيئة في Render.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


class HealthCheckHandler(BaseHTTPRequestHandler):
    """خادم بسيط يجيب على طلبات Render للتحقق من أن البوت يعمل."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        # منع ظهور رسائل السيرفر في الكونسول
        pass


def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


def normalize_codec(value):
    if not value or value == "none":
        return "None"
    return str(value).split(".")[0].upper()


def get_resolution_name(format_data):
    resolution = format_data.get("resolution")
    if resolution and resolution != "none":
        return str(resolution)
    return "غير محدد"


def get_size_label(format_data):
    size_bytes = format_data.get("filesize_approx") or format_data.get("filesize") or 0
    if not size_bytes:
        return "حجم تلقائي"
    size_mb = round(size_bytes / 1024 / 1024, 1)
    return f"{size_mb} MB"


def build_format_button(format_data):
    resolution = get_resolution_name(format_data)
    vcodec = normalize_codec(format_data.get("vcodec"))
    acodec = normalize_codec(format_data.get("acodec"))
    size_label = get_size_label(format_data)
    format_id = format_data.get("format_id", "unknown")
    label = f"📹 {resolution} | {vcodec}/{acodec} | {size_label}"
    return label, f"dl_{format_id}"


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    bot.reply_to(
        message,
        "<b>مرحباً بك في بوت التحميل من يوتيوب!</b>\n"
        "أرسل لي رابط الفيديو، وسأعرض لك الخيارات المتاحة من الجودة والصوت والترجمة."
    )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text is None:
        bot.reply_to(message, "يرجى إرسال رابط فيديو صحيح.")
        return

    url = message.text.strip()
    if "youtube.com" not in url and "youtu.be" not in url:
        bot.reply_to(message, "يرجى إرسال رابط يوتيوب صحيح.")
        return

    bot.reply_to(message, "جاري فحص الرابط واستخراج الخيارات المتاحة...")

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "listformats": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = info.get("formats", [])
        if not formats:
            bot.reply_to(message, "لم أجد أي جودة متاحة لهذا الرابط، حاول رابطاً آخر.")
            return

        # ترتيب أفضل حسب الدقة وحجم الملف
        filtered = []
        for f in formats:
            vcodec = f.get("vcodec")
            acodec = f.get("acodec")
            if vcodec == "none" or acodec == "none":
                continue
            if f.get("format_id") is None:
                continue
            filtered.append(f)

        filtered.sort(key=lambda f: (
            int(f.get("height") or 0),
            int(f.get("filesize_approx") or f.get("filesize") or 0),
            str(f.get("format_id", ""))
        ), reverse=True)

        markup = InlineKeyboardMarkup()
        seen = set()

        for f in filtered:
            label, callback_data = build_format_button(f)
            if callback_data in seen:
                continue
            seen.add(callback_data)
            markup.add(InlineKeyboardButton(text=label, callback_data=callback_data))

        if not markup.keyboard:
            bot.reply_to(message, "لم أجد أي تنسيقات فيديو مناسبة لهذا الرابط.")
            return

        bot.send_message(
            message.chat.id,
            "اختر الجودة المناسبة لك من القائمة:",
            reply_markup=markup,
        )

    except Exception as e:
        bot.reply_to(message, f"حدث خطأ أثناء الفحص: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("dl_"))
def handle_callback(call):
    format_id = call.data.replace("dl_", "")
    bot.answer_callback_query(call.id, f"تم اختيار الفيديو: {format_id}")
    bot.send_message(
        call.message.chat.id,
        f"<b>تم اختيار التنسيق:</b> <code>{format_id}</code>\n"
        "يمكنك الآن استخدام هذا التنسيق في مرحلة التحديث القادمة أو ربطه بتحميل مباشر."
    )


if __name__ == "__main__":
    # تشغيل خادم Render health check في الخلفية
    threading.Thread(target=run_health_server, daemon=True).start()
    # تشغيل البوت
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
