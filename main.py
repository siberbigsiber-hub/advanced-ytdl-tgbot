import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# جلب التوكن بأمان
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# كود سحري لفتح بورت وهمي لإرضاء سيرفر ريندر المجاني
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً بك في بوت التحميل المطور! أرسل لي رابط فيديو من يوتيوب لتعرض كل الترميزات والجودات والدبلجات المتاحة.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text
    if "youtube.com" in url or "youtu.be" in url:
        bot.reply_to(message, "جاري فحص الرابط واستخراج الترميزات ومسارات الصوت والترجمة من سيرفرات يوتيوب...")
        ydl_opts = {'listformats': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                markup = InlineKeyboardMarkup()

                for f in formats:
                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                        resolution = f.get('resolution', 'Unknown')
                        vcodec = f.get('vcodec', 'Unknown').split('.')
                        acodec = f.get('acodec', 'Unknown').split('.')
                        size = f.get('filesize_approx', 0)
                        size_mb = f"{round(size / 1024 / 1024, 1)}MB" if size else "حجم تلقائي"

                        btn_text = f"جودة {resolution} ({vcodec}/{acodec}) [{size_mb}]"
                        markup.add(InlineKeyboardButton(text=btn_text, callback_data=f"dl_{f['format_id']}"))

                bot.send_message(message.chat.id, "اختر الترميز والجودة المناسبة الموفرة لباقتك:", reply_markup=markup)
            except Exception as e:
                bot.reply_to(message, f"حدث خطأ أثناء الفحص: {str(e)}")
    else:
        bot.reply_to(message, "يرجى إرسال رابط يوتيوب صحيح.")

if __name__ == "__main__":
    # تشغيل البورت الوهمي في الخلفية
    threading.Thread(target=run_health_server, daemon=True).start()
    # تشغيل البوت
    bot.infinity_polling()
