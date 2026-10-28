import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# جلب التوكن بأمان من سيرفر ريندر
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

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
                # فرز وعرض الترميزات والجودات المتاحة للفيديو
                for f in formats:
                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                        resolution = f.get('resolution', 'Unknown')
                        vcodec = f.get('vcodec', 'Unknown').split('.')[0]
                        acodec = f.get('acodec', 'Unknown').split('.')[0]
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
    bot.infinity_polling()
