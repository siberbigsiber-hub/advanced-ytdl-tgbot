# Advanced YouTube Downloader Telegram Bot

بوت Telegram يعمل على جلب رابط فيديو من YouTube، وعرض الترميزات المتاحة فقط في صورة متوافقة مع الحاويات المهمة في المشروع:

- MP4 Compatible
- WebM Compatible
- Audio track selection
- Video quality selection
- Subtitle selection when available
- Estimated size before download
- One active download per chat
- Cancel and logs support
- FFmpeg mux without heavy re-encoding

ملاحظات مهمة:
- هذا المشروع مصمم للـ RAM منخفضة (512MB) بشكل أساسي.
- لا يتم إعادة ترميز الفيديو بشكل كامل، بل يتم استخدام دمج الحاوية فقط أو MUXING مع الترميزات المتوافقة.
- لا توجد دبلجة في كل فيديوهات YouTube، لذلك يتم التعامل معها كميزة اختيارية فقط إذا كانت متاحة في metadata.
- هذا المشروع مناسب جدًا لـ Render أو Docker أو VPS خفيف.

## المتطلبات

- Python 3.10+
- FFmpeg
- Telegram Bot Token

## تثبيت المتطلبات

```bash
pip install -r requirements.txt
```

## إعداد المتغيرات

أضف هذه المتغيرات إلى البيئة:

```bash
export BOT_TOKEN="YOUR_BOT_TOKEN"
export PORT="10000"
```

## التشغيل محليًا

```bash
python main.py
```

## التشغيل عبر Docker

```bash
docker build -t ytbot .
docker run -d --name ytbot -e BOT_TOKEN="YOUR_BOT_TOKEN" -e PORT=10000 -p 10000:10000 ytbot
```

## التشغيل على Render

1. أنشئ مشروع Docker في Render.
2. اربط مستودع GitHub.
3. أضف المتغيرات:
   - BOT_TOKEN
   - PORT (معظم الأوقات يحدده Render تلقائيًا)
4. ابدأ الخدمة.

## كيفية الاستخدام

1. أرسل رابط YouTube إلى البوت.
2. اختر نوع الحاوية: MP4 أو WebM.
3. اختر الصوت المناسب.
4. اختر الفيديو المناسب.
5. اختر الترجمة إن وجدت.
6. اكتب `/merge` لبدء الدمج والتحميل.
7. يمكنك إيقاف التنزيل أثناء العمل أو عرض السجلات.

## ملاحظات التنفيذ

- هذا المشروع يخفّض استهلاك الـ RAM من خلال:
  - تنزيل واحد فقط لكل محادثة
  - عدم است��دام إعادة ترميز الفيديو الثقيلة
  - دمج الحاويات فقط مع الترميزات المتوافقة
- إذا لم يجد أي ترميز متوافق، سيطلب من المستخدم اختيار نوع آخر أو يعطي رسالة مناسبة.

## ملاحظة مهمة عن الدبلجة

الدبلجة ليست متاحة دائمًا في YouTube، لذلك لا يتم الإعلان عنها كميزة أساسية في كل الفيديوهات. يتم التعامل معها فقط كـ audio alt إذا كانت موجودة في metadata، وليس كخيار افتراضي.

## الأمان والاستقرار

- يضمن health check لأغراض Render
- ينظف الملفات المؤقتة بعد كل عملية
- لا يسمح بتحميل متعدد في نفس المحادثة
- يضع حدًا عمليًا لسهولة التشغيل على الخوادم الصغيرة
