import os
import io
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

# --- الإعدادات الرئيسية ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
WATERMARK_TEXT = "صياد العروض"
FONT_PATH = "NotoSansArabic-Regular.ttf"
FONT_SIZE = 35
# اللون الافتراضي (سيتم استخدامه إذا لم يختر المستخدم لونًا)
DEFAULT_FONT_COLOR = (0, 0, 0, 128) # أسود

# --- خادم الويب لإبقاء البوت يعمل ---
app = Flask(__name__)

@app.route('/')
def home():
    """صفحة ويب بسيطة تستخدمها خدمات المراقبة لإبقاء البوت نشطًا."""
    return "Bot is running!"

def run_flask():
    """تشغيل خادم الويب في خيط منفصل."""
    app.run(host='0.0.0.0', port=8080)

# --- دالة إضافة العلامة المائية على الصور ---
def add_watermark(input_image_stream, font_color):
    """
    تضيف علامة مائية نصية موزعة على الصورة بجودة عالية.
    """
    try:
        # فتح الصورة وتحويلها لدعم الشفافية
        image = Image.open(input_image_stream).convert("RGBA")
        txt_layer = Image.new("RGBA", image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)

        # معالجة النص العربي لضمان عرضه بشكل صحيح (ترتيب الكلمات واتصال الحروف)
        reshaped_text = arabic_reshaper.reshape(WATERMARK_TEXT)
        bidi_text = get_display(reshaped_text)

        # تحميل الخط
        try:
            font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        except IOError:
            print(f"خطأ: لم يتم العثور على ملف الخط في المسار: {FONT_PATH}")
            return None

        # حساب أبعاد النص لتحديد المسافات بين العلامات
        text_bbox = draw.textbbox((0, 0), bidi_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # تحديد المسافات الأفقية والرأسية بين كل علامة
        x_step = text_width + 200
        y_step = text_height + 150

        # حلقة لتوزيع العلامة المائية على كامل مساحة الصورة
        for x in range(0, image.width, x_step):
            for y in range(0, image.height, y_step):
                position = (x, y)
                # استخدام متغير اللون بدلاً من اللون الثابت
                draw.text(position, bidi_text, font=font, fill=font_color)

        # دمج طبقة النص مع الصورة الأصلية
        watermarked_image = Image.alpha_composite(image, txt_layer)

        # حفظ الصورة النهائية في الذاكرة لإرسالها
        output_stream = io.BytesIO()
        # حفظ الصورة بجودة عالية (95%) لمنع انخفاض الجودة
        watermarked_image.convert("RGB").save(output_stream, format='JPEG', quality=95)
        output_stream.seek(0)
        return output_stream
    except Exception as e:
        print(f"حدث خطأ أثناء معالجة الصورة: {e}")
        return None

# --- معالجات أوامر البوت ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يرسل رسالة ترحيبية عند بدء تشغيل البوت."""
    welcome_message = """
مرحباً بك في بوت حقوق "صياد العروض"! 📸

وظيفتي هي إضافة العلامة المائية "صياد العروض" على أي صورة ترسلها لي للحفاظ على حقوقك.

** كيف تستخدم البوت؟ **
- أرسل صورة مباشرةً لوضع العلامة المائية عليها باللون الافتراضي (أسود).
- لتغيير لون العلامة المائية، استخدم الأمر /color.
"""
    await update.message.reply_text(welcome_message)

async def color_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يرسل رسالة مع أزرار لاختيار اللون."""
    keyboard = [
        [
            InlineKeyboardButton("⚫️ أسود", callback_data='color_black'),
            InlineKeyboardButton("🔴 أحمر", callback_data='color_red'),
        ],
        [
            InlineKeyboardButton("🔵 أزرق", callback_data='color_blue')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر لون العلامة المائية:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج ضغطات الأزرار ويحفظ اختيار اللون."""
    query = update.callback_query
    await query.answer()

    # تعريف الألوان المتاحة
    color_map = {
        'color_black': {'name': 'الأسود', 'value': (0, 0, 0, 128)},
        'color_red': {'name': 'الأحمر', 'value': (255, 0, 0, 128)},
        'color_blue': {'name': 'الأزرق', 'value': (0, 0, 255, 128)},
    }

    choice = query.data
    if choice in color_map:
        selected_color = color_map[choice]
        # حفظ اختيار المستخدم في user_data
        context.user_data['font_color'] = selected_color['value']
        await query.edit_message_text(text=f"✅ تم اختيار اللون: {selected_color['name']}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج الصور المستلمة من المستخدم."""
    await update.message.reply_text("جاري معالجة الصورة، يرجى الانتظار...")
    try:
        # جلب اللون الذي اختاره المستخدم، أو استخدام اللون الافتراضي
        font_color = context.user_data.get('font_color', DEFAULT_FONT_COLOR)

        photo_file = await context.bot.get_file(update.message.photo[-1].file_id)
        input_stream = io.BytesIO()
        await photo_file.download_to_memory(input_stream)
        input_stream.seek(0)

        # تمرير اللون المختار إلى دالة إضافة العلامة المائية
        watermarked_photo_stream = add_watermark(input_stream, font_color)

        if watermarked_photo_stream:
            await update.message.reply_photo(photo=watermarked_photo_stream, caption="تمت إضافة الحقوق بنجاح!")
        else:
            await update.message.reply_text("عذراً، حدث خطأ أثناء إضافة الحقوق.")
    except Exception as e:
        print(f"خطأ في معالجة الصورة: {e}")
        await update.message.reply_text("حدث خطأ غير متوقع.")

# --- الدالة الرئيسية لتشغيل البوت ---
def main():
    """الدالة الرئيسية التي تقوم بإعداد وتشغيل البوت."""
    if not TOKEN:
        print("خطأ فادح: لم يتم العثور على توكن التيليجرام.")
        return

    # تشغيل خادم الويب في الخلفية
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    print("البوت قيد التشغيل...")
    # بناء تطبيق البوت
    application = Application.builder().token(TOKEN).build()

    # إضافة المعالجات للأوامر والصور
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("color", color_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # بدء تشغيل البوت
    application.run_polling()

if __name__ == '__main__':
    main()