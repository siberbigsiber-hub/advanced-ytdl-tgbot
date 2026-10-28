import os
import shutil
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import quote, unquote

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN غير موجود. أضفه إلى متغيرات البيئة في Render.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        pass


def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


def clean_text(value, default="Unknown"):
    if value is None:
        return default
    return str(value)


def estimate_size_mb(format_data):
    if format_data.get("filesize_approx"):
        return round(format_data["filesize_approx"] / 1024 / 1024, 2)
    if format_data.get("filesize"):
        return round(format_data["filesize"] / 1024 / 1024, 2)
    bitrate = format_data.get("tbr") or 0
    duration = format_data.get("duration") or 0
    if bitrate and duration:
        return round((bitrate * duration) / (8 * 1024), 2)
    return 0


def codec_name(value):
    v = clean_text(value, "")
    if v in ("", "none", "None"):
        return "-"
    return v.split(".")[0].upper()


def normalize_resolution(format_data):
    height = format_data.get("height")
    if height:
        return f"{height}p"
    return "-"


def get_subtitles_summary(subtitles, auto_caps):
    all_subs = []
    for lang, v in (subtitles or {}).items():
        all_subs.append(f"{lang}")
    for lang, v in (auto_caps or {}).items():
        all_subs.append(f"{lang} (auto)")
    unique = []
    seen = set()
    for item in all_subs:
        if item not in seen:
            unique.append(item)
            seen.add(item)
    return unique


def extract_formats(url):
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = info.get("formats", [])
    audio_formats = []
    video_formats = []
    subtitles = info.get("subtitles") or {}
    auto_caps = info.get("automatic_captions") or {}

    for fmt in formats:
        format_id = fmt.get("format_id")
        if not format_id:
            continue

        ext = fmt.get("ext") or "-"
        size_mb = estimate_size_mb(fmt)
        vcodec = clean_text(fmt.get("vcodec"), "none")
        acodec = clean_text(fmt.get("acodec"), "none")
        resolution = normalize_resolution(fmt)

        if vcodec != "none" and acodec == "none":
            video_formats.append({
                "format_id": format_id,
                "codec": codec_name(vcodec),
                "resolution": resolution,
                "ext": ext,
                "size_mb": size_mb,
                "tbr": fmt.get("tbr"),
                "height": fmt.get("height"),
                "width": fmt.get("width"),
            })

        if vcodec == "none" and acodec != "none":
            audio_formats.append({
                "format_id": format_id,
                "codec": codec_name(acodec),
                "ext": ext,
                "size_mb": size_mb,
                "abr": fmt.get("abr"),
                "tbr": fmt.get("tbr"),
            })

    audio_formats.sort(key=lambda item: (item["size_mb"], item["format_id"]), reverse=True)
    video_formats.sort(key=lambda item: ((item["height"] or 0), item["size_mb"]), reverse=True)

    return info, audio_formats, video_formats, subtitles, auto_caps


def build_menu_markup(url):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(text="🎵 الصوت", callback_data=f"menu|audio|{quote(url)}"),
        InlineKeyboardButton(text="📹 الفيديو", callback_data=f"menu|video|{quote(url)}")
    )
    markup.add(
        InlineKeyboardButton(text="📝 الترجمات", callback_data=f"menu|subs|{quote(url)}"),
        InlineKeyboardButton(text="📊 تقدير الحجم", callback_data=f"menu|stats|{quote(url)}")
    )
    return markup


def filter_formats_by_codec(items, codec):
    if not codec:
        return items
    needle = codec.lower()
    return [item for item in items if needle in str(item.get("codec", "")).lower()]


def build_format_buttons(items, prefix, url, max_items=12):
    markup = InlineKeyboardMarkup()
    for item in items[:max_items]:
        label = ""
        if prefix == "audio":
            codec = item.get("codec", "-")
            abr = item.get("abr") or "-"
            size = item.get("size_mb")
            size_txt = f"{size} MB" if size else "حجم غير محدد"
            label = f"🎵 {codec} | abr {abr} | {size_txt}"
        elif prefix == "video":
            codec = item.get("codec", "-")
            resolution = item.get("resolution", "-")
            size = item.get("size_mb")
            size_txt = f"{size} MB" if size else "حجم غير محدد"
            label = f"📹 {resolution} | {codec} | {size_txt}"
        else:
            label = item
        callback_data = f"pick|{prefix}|{item.get('format_id', item)}|{quote(url)}"
        markup.add(InlineKeyboardButton(text=label, callback_data=callback_data))
    return markup


def pass_to_filter_message(chat_id, text, markup):
    bot.send_message(chat_id, text, reply_markup=markup)


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    bot.reply_to(
        message,
        "<b>مرحباً بك في بوت يوتيوب المتقدم</b>\n"
        "أرسل رابط الفيديو، ثم سيتم عرض:\n"
        "• كل ترميزات الصوت\n"
        "• كل ترميزات الفيديو\n"
        "• الترجمات إن وجدت\n"
        "• تقدير الحجم قبل التنزيل\n"
        "ملاحظة: الدبلجة لا تظهر دائماً في يوتيوب إلا إذا وفّرها الفيديو نفسه."
    )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if not message.text:
        bot.reply_to(message, "يرجى إرسال رابط يوتيوب صحيح.")
        return

    url = message.text.strip()
    if "youtube.com" not in url and "youtu.be" not in url:
        bot.reply_to(message, "يرجى إرسال رابط يوتيوب صحيح.")
        return

    bot.reply_to(message, "جاري فحص الرابط واستخراج كل الترميزات المتاحة...")

    try:
        info, audio_formats, video_formats, subtitles, auto_caps = extract_formats(url)
        title = clean_text(info.get("title"), "فيديو")
        subtitle_list = get_subtitles_summary(subtitles, auto_caps)

        markup = build_menu_markup(url)
        text = (
            f"<b>{title}</b>\n\n"
            f"🎵 صوت متاح: {len(audio_formats)}\n"
            f"📹 فيديو متاح: {len(video_formats)}\n"
            f"📝 ترجمات متاحة: {len(subtitle_list)}\n\n"
            "اختر ما تريد عرضه:" 
        )
        bot.send_message(message.chat.id, text, reply_markup=markup)
    except Exception as e:
        bot.reply_to(message, f"حدث خطأ أثناء فحص الرابط: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("menu|"))
def handle_menu(call):
    try:
        _, kind, enc_url = call.data.split("|", 2)
        url = unquote(enc_url)
    except ValueError:
        bot.answer_callback_query(call.id, "بيانات غير صالحة")
        return

    try:
        info, audio_formats, video_formats, subtitles, auto_caps = extract_formats(url)
        title = clean_text(info.get("title"), "فيديو")
        subtitle_list = get_subtitles_summary(subtitles, auto_caps)

        if kind == "audio":
            markup = build_format_buttons(audio_formats, "audio", url)
            bot.send_message(
                call.message.chat.id,
                f"<b>{title}</b>\n🎵 جميع ترميزات الصوت المتاحة:",
                reply_markup=markup,
            )
            return

        if kind == "video":
            markup = build_format_buttons(video_formats, "video", url)
            bot.send_message(
                call.message.chat.id,
                f"<b>{title}</b>\n📹 جميع ترميزات الفيديو المتاحة:",
                reply_markup=markup,
            )
            return

        if kind == "subs":
            if not subtitle_list:
                bot.send_message(call.message.chat.id, "لا توجد ترجمات أو تعليقات متاحة لهذا الفيديو.")
                return
            markup = InlineKeyboardMarkup()
            for lang in subtitle_list[:20]:
                markup.add(InlineKeyboardButton(text=f"📝 {lang}", callback_data=f"pick|subs|{lang}|{quote(url)}"))
            bot.send_message(call.message.chat.id, f"<b>{title}</b>\nاختر اللغة للترجمة:", reply_markup=markup)
            return

        if kind == "stats":
            total_audio = sum(item.get("size_mb", 0) for item in audio_formats)
            total_video = sum(item.get("size_mb", 0) for item in video_formats)
            best_audio = audio_formats[0] if audio_formats else None
            best_video = video_formats[0] if video_formats else None
            message = (
                f"<b>{title}</b>\n\n"
                f"📊 تقدير الحجم الكلي: {round(total_audio + total_video, 2)} MB\n"
                f"🎵 أفضل صوت: {best_audio.get('codec', '-')} / {best_audio.get('size_mb', 0)} MB\n" if best_audio else "🎵 لا يوجد صوت متاح\n"
                f"📹 أفضل فيديو: {best_video.get('resolution', '-')} / {best_video.get('codec', '-')} / {best_video.get('size_mb', 0)} MB\n" if best_video else "📹 لا يوجد فيديو متاح\n"
            )
            bot.send_message(call.message.chat.id, message)
            return

    except Exception as e:
        bot.send_message(call.message.chat.id, f"حدث خطأ: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("pick|"))
def handle_pick(call):
    try:
        _, kind, value, enc_url = call.data.split("|", 3)
        url = unquote(enc_url)
    except ValueError:
        bot.answer_callback_query(call.id, "بيانات الاختيار غير صالحة")
        return

    if kind == "subs":
        bot.answer_callback_query(call.id, f"تم اختيار الترجمة: {value}")
        bot.send_message(call.message.chat.id, f"تم اختيار اللغة: <b>{value}</b>\nيمكنك لاحقًا تحميل الترجمة مباشرة إن توفر هذا الفيديو لها.")
        return

    format_id = value
    if kind not in {"audio", "video"}:
        bot.answer_callback_query(call.id, "نوع الاختيار غير معروف")
        return

    bot.answer_callback_query(call.id, f"تم اختيار {kind} - format_id: {format_id}")
    bot.send_message(
        call.message.chat.id,
        f"<b>تم اختيار {kind}</b>\n<code>format_id = {format_id}</code>\n\n"
        "هذا هو رقم التنسيق، ويجب دمجه مع رابط الفيديو عند تنفيذ التحميل الفعلي.\n"
        "لإعداد التشغيل الكامل نحتاج أيضًا إلى ffmpeg للدمج بين الصوت والفيديو إذا أردنا الحصول على نسخة نهائية." 
    )


if __name__ == "__main__":
    threading.Thread(target=run_health_server, daemon=True).start()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
