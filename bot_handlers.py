import os
import shutil
import tempfile
import threading
from urllib.parse import quote, unquote

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

from config import BOT_TOKEN
from merge_tools import mux_streams
from youtube_utils import extract_metadata, BotProtectedVideoError

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
ACTIVE_JOBS = {}


def safe_text(value):
    return str(value).replace("<", "&lt;").replace(">", "&gt;")


def protected_video_notice():
    return (
        "<b>هذا الفيديو محمي بنظام أمان YouTube</b>\n\n"
        "أسباب شائعة:\n"
        "• الفيديو يحتاج كوكيز جديدة أو جلسة متصفح\n"
        "• أو أنه محمي/مقيد من YouTube\n"
        "• أو أن الرابط من فيديو خاص/مقيد\n\n"
        "حاول بإرسال فيديو عام/public، أو استخدم ملف كوكيز جديد من متصفحك.\n"
        "إذا كان الرابط محميًا، البوت لا يستطيع تخطي حماية YouTube بدون كوكيز أو جلسة فعّالة."
    )


def build_choose_container(url):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📦 MP4 Compatible", callback_data=f"container|mp4|{quote(url)}"),
        InlineKeyboardButton("📦 WebM Compatible", callback_data=f"container|webm|{quote(url)}"),
    )
    return markup


def build_audio_buttons(audio_items, url, container):
    markup = InlineKeyboardMarkup()
    for item in audio_items[:12]:
        label = f"🎵 {item['codec']} | {item['size_mb']} MB"
        markup.add(
            InlineKeyboardButton(
                text=label,
                callback_data=f"pick|audio|{item['format_id']}|{container}|{quote(url)}"
            )
        )
    return markup


def build_video_buttons(video_items, url, container):
    markup = InlineKeyboardMarkup()
    for item in video_items[:12]:
        label = f"📹 {item['resolution']} | {item['codec']} | {item['size_mb']} MB"
        markup.add(
            InlineKeyboardButton(
                text=label,
                callback_data=f"pick|video|{item['format_id']}|{container}|{quote(url)}"
            )
        )
    return markup


def build_subtitle_buttons(subtitles, url):
    markup = InlineKeyboardMarkup()
    for lang in subtitles[:20]:
        markup.add(
            InlineKeyboardButton(
                text=f"📝 {lang}",
                callback_data=f"pick|sub|{lang}|none|{quote(url)}"
            )
        )
    markup.add(
        InlineKeyboardButton("🚫 لا شيء", callback_data=f"pick|sub|none|none|{quote(url)}")
    )
    return markup


def build_status_message(job):
    return (
        f"<b>الحالة:</b> {job['status']}<br>"
        f"<b>التقدم:</b> {job['progress']}<br>"
        f"<b>السرعة:</b> {job['speed']}<br>"
        f"<b>التحميل:</b> {job['downloaded']} / {job['total']}"
    )


def build_after_menu():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📥 تحميل فيديو جديد", callback_data="new_video"),
        InlineKeyboardButton("📝 عرض السجلات", callback_data="show_logs"),
    )
    return markup


def build_cancel_menu():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("⏹ إيقاف التنزيل", callback_data="cancel_download")
    )
    return markup


def download_format(url, format_id, output_path):
    ydl_opts = {
        "format": format_id,
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


@bot.message_handler(commands=["start", "help"])
def start_cmd(message):
    bot.reply_to(
        message,
        "<b>مرحباً بك في بوت يوتيوب المتقدم</b>\n\n"
        "أرسل رابط الفيديو، ثم اختر نوع الحاوية:\n"
        "• MP4 Compatible\n"
        "• WebM Compatible\n"
        "• ترجمة إن وجدت\n\n"
        "ملاحظة: بعض فيديوهات YouTube محمية أو تحتاج كوكيز/جلسة جديدة.\n"
        "البوت سيحاول التعامل معها بشكل ذكي."
    )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = (message.text or "").strip()
    if not text:
        bot.reply_to(message, "يرجى إرسال رابط يوتيوب صحيح.")
        return

    if "youtube.com" not in text and "youtu.be" not in text:
        bot.reply_to(message, "يرجى إرسال رابط يوتيوب صحيح.")
        return

    if message.chat.id in ACTIVE_JOBS:
        existing = ACTIVE_JOBS[message.chat.id]
        if existing.get("status") in ("جاري التنزيل", "جاهز"):
            bot.reply_to(message, "⚠ يوجد تنزيل فعلي قيد التنفيذ في هذه المحادثة. انتظر حتى ينتهي أو أوقفه.")
            return

    try:
        info = extract_metadata(text)
        title = safe_text(info["title"])

        ACTIVE_JOBS[message.chat.id] = {
            "state": {
                "url": text,
                "title": title,
                "selected_audio": None,
                "selected_video": None,
                "selected_subtitle": None,
                "container": None,
            },
            "status": "جاهز",
            "progress": "0%",
            "speed": "0 KB/s",
            "downloaded": "0",
            "total": "0",
            "logs": [],
            "stop_event": None,
            "message_id": None,
            "job_thread": None,
        }

        bot.send_message(
            message.chat.id,
            f"<b>{title}</b>\n\n"
            f"🎵 أصوات MP4: {len(info['audio']['mp4_audio'])}\n"
            f"🎵 أصوات WebM: {len(info['audio']['webm_audio'])}\n"
            f"📹 فيديو MP4: {len(info['audio']['mp4_video'])}\n"
            f"📹 فيديو WebM: {len(info['audio']['webm_video'])}\n"
            f"📝 ترجمات: {len(info['subtitles'])}\n\n"
            "اختر نوع الحاوية:",
            reply_markup=build_choose_container(text),
        )

    except BotProtectedVideoError:
        bot.reply_to(message, protected_video_notice())
    except Exception as exc:
        bot.reply_to(message, f"حدث خطأ أثناء تجهيز الفيديو: {str(exc)}")


@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("container|"))
def handle_container(call):
    try:
        _, container, enc_url = call.data.split("|", 2)
        url = unquote(enc_url)
    except Exception:
        bot.answer_callback_query(call.id, "بيانات غير صالحة.")
        return

    job = ACTIVE_JOBS.get(call.message.chat.id)
    if not job:
        bot.send_message(call.message.chat.id, "لا توجد جلسة سابقة.")
        return

    state = job["state"]
    state["url"] = url
    state["container"] = container

    try:
        info = extract_metadata(url)
        title = safe_text(info["title"])

        if container == "mp4":
            audio_items = info["audio"]["mp4_audio"]
            video_items = info["audio"]["mp4_video"]
        else:
            audio_items = info["audio"]["webm_audio"]
            video_items = info["audio"]["webm_video"]

        if not audio_items or not video_items:
            bot.send_message(
                call.message.chat.id,
                f"<b>{title}</b>\nلا توجد ترميزات متوافقة مباشرة مع <b>{container.upper()}</b>. جرّب نوع حاوية آخر."
            )
            return

        audio_markup = build_audio_buttons(audio_items, url, container)
        video_markup = build_video_buttons(video_items, url, container)

        bot.send_message(
            call.message.chat.id,
            f"<b>{title}</b>\n📦 الحاوية: {container.upper()}\nاختر الصوت:",
            reply_markup=audio_markup,
        )

        bot.send_message(
            call.message.chat.id,
            f"<b>{title}</b>\n📦 الحاوية: {container.upper()}\nاختر جودة الفيديو:",
            reply_markup=video_markup,
        )

        if info["subtitles"]:
            sub_markup = build_subtitle_buttons(info["subtitles"], url)
            bot.send_message(
                call.message.chat.id,
                f"<b>{title}</b>\n📝 اختر الترجمة إن وجدت:",
                reply_markup=sub_markup,
            )
        else:
            bot.send_message(call.message.chat.id, f"<b>{title}</b>\nلا توجد ترجمات متاحة لهذا الفيديو.")
    except BotProtectedVideoError:
        bot.send_message(call.message.chat.id, protected_video_notice())
    except Exception as exc:
        bot.send_message(call.message.chat.id, f"حدث خطأ أثناء تجهيز الخيارات: {str(exc)}")


@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("pick|"))
def handle_pick(call):
    try:
        _, kind, value, container, enc_url = call.data.split("|", 4)
        url = unquote(enc_url)
    except Exception:
        bot.answer_callback_query(call.id, "بيانات الاختيار غير صالحة.")
        return

    job = ACTIVE_JOBS.get(call.message.chat.id)
    if not job:
        return

    state = job["state"]
    state["url"] = url
    state["container"] = container

    if kind == "audio":
        state["selected_audio"] = value
        bot.answer_callback_query(call.id, f"تم اختيار الصوت: {value}")
        bot.send_message(call.message.chat.id, f"تم اختيار الصوت: <code>{value}</code>\nالآن اختر الفيديو المناسب.")
        return

    if kind == "video":
        state["selected_video"] = value
        bot.answer_callback_query(call.id, f"تم اختيار الفيديو: {value}")
        bot.send_message(call.message.chat.id, f"تم اختيار الفيديو: <code>{value}</code>\nالآن اختر الترجمة إن وجدت، أو اكتب /merge إذا كنت جاهزًا.")
        return

    if kind == "sub":
        state["selected_subtitle"] = value
        bot.answer_callback_query(call.id, f"تم اختيار الترجمة: {value}")
        bot.send_message(call.message.chat.id, f"تم اختيار الترجمة: <b>{value}</b>")
        return


@bot.message_handler(commands=["merge"])
def merge_command(message):
    job = ACTIVE_JOBS.get(message.chat.id)
    if not job:
        bot.reply_to(message, "لا توجد جلسة فيديو مفتوحة. أرسل رابط فيديو أولاً.")
        return

    state = job["state"]
    url = state.get("url")
    audio_id = state.get("selected_audio")
    video_id = state.get("selected_video")
    container = state.get("container")

    if not url or not audio_id or not video_id or not container:
        bot.reply_to(message, "يجب أولاً اختيار: نوع الحاوية + الصوت + الفيديو.")
        return

    if job.get("status") == "جاري التنزيل":
        bot.reply_to(message, "⚠ يوجد تحميل فعلي قيد التنفيذ في هذه المحادثة.")
        return

    temp_dir = tempfile.mkdtemp(prefix="ytbot_")
    stop_event = threading.Event()

    job["status"] = "جاري التنزيل"
    job["progress"] = "0%"
    job["speed"] = "0 KB/s"
    job["downloaded"] = "0"
    job["total"] = "0"
    job["logs"] = []
    job["stop_event"] = stop_event
    job["temp_dir"] = temp_dir

    sent = bot.reply_to(message, "🔄 جاري تجهيز تحميل الفيديو...")
    job["message_id"] = sent.message_id

    def progress_hook(d):
        if stop_event.is_set():
            raise RuntimeError("تم إلغاء التنزيل")

        if d["status"] == "downloading":
            job["status"] = "جاري التنزيل"
            job["progress"] = d.get("_percent_str", "0%").strip()
            job["speed"] = d.get("_speed_str", "0 KB/s")
            job["downloaded"] = d.get("_downloaded_bytes_str", "0")
            job["total"] = d.get("_total_bytes_str", "0")
            job["logs"].append(f"{job['progress']} | {job['speed']}")

            try:
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=job["message_id"],
                    text=build_status_message(job),
                    reply_markup=build_cancel_menu(),
                )
            except Exception:
                pass

    def worker():
        audio_path = os.path.join(temp_dir, f"audio.{container}")
        video_path = os.path.join(temp_dir, f"video.{container}")
        output_path = os.path.join(temp_dir, f"final_output.{container}")

        try:
            ydl_audio_opts = {
                "format": audio_id,
                "outtmpl": audio_path,
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "progress_hooks": [progress_hook],
            }
            cookies_file = os.getenv("YT_COOKIES_FILE")
            if cookies_file and os.path.exists(cookies_file):
                ydl_audio_opts["cookies"] = cookies_file

            with yt_dlp.YoutubeDL(ydl_audio_opts) as ydl:
                ydl.download([url])

            ydl_video_opts = {
                "format": video_id,
                "outtmpl": video_path,
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "progress_hooks": [progress_hook],
            }
            if cookies_file and os.path.exists(cookies_file):
                ydl_video_opts["cookies"] = cookies_file

            with yt_dlp.YoutubeDL(ydl_video_opts) as ydl:
                ydl.download([url])

            mux_streams(video_path, audio_path, output_path, container)

            with open(output_path, "rb") as file:
                bot.send_video(message.chat.id, file, supports_streaming=True, caption=f"✅ {state['title']}")

            job["status"] = "تم الإرسال"
            job["logs"].append("تم إرسال الملف إلى Telegram")
            bot.send_message(message.chat.id, "✅ تم إنجاز التنزيل بنجاح.", reply_markup=build_after_menu())

        except BotProtectedVideoError:
            job["status"] = "مقيد"
            job["logs"].append("الفيديو محمي ويحتاج كوكيز/جلسة جديدة من YouTube")
            bot.send_message(message.chat.id, protected_video_notice())
        except RuntimeError as exc:
            if "تم إلغاء التنزيل" in str(exc):
                job["status"] = "تم الإلغاء"
                job["logs"].append("تم إلغاء التنزيل")
                bot.send_message(message.chat.id, "⏹ تم إلغاء التنزيل.")
            else:
                job["status"] = "فشل"
                job["logs"].append(f"فشل: {str(exc)}")
                bot.send_message(message.chat.id, f"❌ فشل التنزيل: {str(exc)}")
        except Exception as exc:
            err_msg = str(exc).lower()
            if (
                "sign in to confirm you’re not a bot" in err_msg
                or "sign in to confirm you are not a bot" in err_msg
                or "cookies" in err_msg
                or "login" in err_msg
                or "authentication" in err_msg
            ):
                job["status"] = "مقيد"
                job["logs"].append("الفيديو محمي بنظام أمان YouTube أو يحتاج كوكيز جديدة.")
                bot.send_message(message.chat.id, protected_video_notice())
            else:
                job["status"] = "فشل"
                job["logs"].append(f"فشل: {str(exc)}")
                bot.send_message(message.chat.id, f"❌ فشل التحميل: {str(exc)}")
        finally:
            try:
                for path in [audio_path, video_path, output_path]:
                    if os.path.exists(path):
                        os.remove(path)
            except Exception:
                pass

            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

            job["stop_event"] = None

    thread = threading.Thread(target=worker, daemon=True)
    job["job_thread"] = thread
    thread.start()


@bot.callback_query_handler(func=lambda call: call.data == "new_video")
def new_video(call):
    ACTIVE_JOBS.pop(call.message.chat.id, None)
    bot.send_message(call.message.chat.id, "أرسل رابط فيديو جديد.")
    bot.answer_callback_query(call.id, "جاهز")


@bot.callback_query_handler(func=lambda call: call.data == "show_logs")
def show_logs(call):
    job = ACTIVE_JOBS.get(call.message.chat.id)
    if not job:
        bot.send_message(call.message.chat.id, "لا يوجد تحميل فعلي.")
        return

    logs = job.get("logs", [])[-20:]
    text = "\n".join(logs) if logs else "لا توجد سجلات بعد."
    bot.send_message(call.message.chat.id, f"<pre>{text}</pre>", parse_mode="HTML")
    bot.answer_callback_query(call.id, "تم عرض السجلات")


@bot.callback_query_handler(func=lambda call: call.data == "cancel_download")
def cancel_download(call):
    job = ACTIVE_JOBS.get(call.message.chat.id)
    if not job:
        bot.send_message(call.message.chat.id, "لا يوجد تنزيل فعلي.")
        return

    stop_event = job.get("stop_event")
    if stop_event:
        stop_event.set()
        job["status"] = "إلغاء قيد التنفيذ"
        bot.answer_callback_query(call.id, "تم إرسال إشارة الإلغاء.")
    else:
        bot.answer_callback_query(call.id, "لا يوجد تنزيل فعلي ليُوقف.")
