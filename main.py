# -*- coding: utf-8 -*-

import os
import io
import threading
import random
import sys
import locale
import asyncio
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
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import arabic_reshaper
from bidi.algorithm import get_display

# ==============================================================================
# ملاحظات هامة للتشغيل
# ==============================================================================
# 1. قم بإنشاء ملف باسم requirements.txt وضع فيه المكتبات التالية:
# python-telegram-bot
# Flask
# Pillow
# arabic_reshaper
# python-bidi
#
# 2. قم بتثبيت المكتبات باستخدام الأمر: pip install -r requirements.txt
#
# 3. لا تضع توكن البوت هنا مباشرة. قم بتعيينه كمتغير بيئة (Environment Variable)
#    باسم TELEGRAM_TOKEN. هذا أكثر أماناً.
# ==============================================================================


# --- ضبط بيئة اللغة العربية ---
# محاولة لضبط اللغة العربية، مع وجود رسالة تحذيرية في حال عدم توفرها
try:
    locale.setlocale(locale.LC_ALL, 'ar_AE.UTF-8')
except locale.Error:
    print("Warning: Arabic locale 'ar_AE.UTF-8' not available. Using default locale.")


# --- الإعدادات الرئيسية ---
# [تحسين أمني] تحميل التوكن من متغيرات البيئة بدلاً من كتابته مباشرة في الكود
TOKEN = os.environ.get("TELEGRAM_TOKEN")
WATERMARK_TEXT = "صياد العروض"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# [تحسين] التأكد من وجود مجلد الخطوط
FONT_DIR = os.path.join(BASE_DIR, "fonts")
if not os.path.exists(FONT_DIR):
    os.makedirs(FONT_DIR)
    print(f"تم إنشاء مجلد الخطوط في: {FONT_DIR}")
    print("الرجاء وضع ملف الخط Amiri-Regular.ttf داخل هذا المجلد.")

FONT_PATH = os.path.join(FONT_DIR, "Amiri-Regular.ttf")
FONT_SIZE = 60
DEFAULT_FONT_COLOR = (0, 0, 0, 180)  # أسود مع شفافية
TEXT_OUTLINE_COLOR = (255, 255, 255, 200)  # لون الحد الأبيض
WATERMARK_OPACITY = 0.5 # [تحسين] ثابت لسهولة التحكم في شفافية العلامة المائية


# --- خادم الويب (لإبقاء البوت يعمل على منصات الاستضافة) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "البوت يعمل بشكل صحيح! ✅"

def run_flask():
    # يعمل على المنفذ الذي توفره منصة الاستضافة أو 8080 كخيار افتراضي
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)


# --- دالة إنشاء علامة مائية نصية ---
def create_text_watermark(text, font_path, font_size, font_color, outline_color):
    """إنشاء صورة شفافة تحتوي على النص العربي مع معالجته."""
    # معالجة النص العربي لعرضه بشكل صحيح
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)

    # تحميل الخط مع معالجة الأخطاء
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"خطأ: لم يتم العثور على الخط في المسار: {font_path}. سيتم استخدام الخط الافتراضي.")
        font = ImageFont.load_default()

    # حساب أبعاد النص بدقة
    text_bbox = font.getbbox(bidi_text)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    # إنشاء صورة شفافة بحجم مناسب للنص مع هوامش
    padding = 20
    watermark_img = Image.new('RGBA', (text_width + padding, text_height + padding), (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark_img)

    # إضافة حد ناعم للنص (لتحسين الوضوح)
    outline_positions = [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]
    for dx, dy in outline_positions:
        draw.text((padding/2 + dx, padding/2 + dy), bidi_text, font=font, fill=outline_color)

    # إضافة النص الرئيسي
    draw.text((padding/2, padding/2), bidi_text, font=font, fill=font_color)

    return watermark_img


# --- دالة إضافة العلامة المائية إلى الصورة ---
def add_watermark(input_image_stream, font_color):
    """
    هذه الدالة تقوم بمعالجة الصورة وهي عملية قد تكون بطيئة (CPU-bound).
    لذلك، يتم تشغيلها في خيط منفصل لتجنب حظر عمل البوت الرئيسي.
    """
    try:
        # فتح الصورة الأساسية
        base_image = Image.open(input_image_stream).convert("RGBA")

        # إنشاء العلامة المائية النصية
        text_watermark = create_text_watermark(
            WATERMARK_TEXT, FONT_PATH, FONT_SIZE, font_color, TEXT_OUTLINE_COLOR
        )

        # إنشاء طبقة شفافة بنفس حجم الصورة الأصلية لوضع العلامات المائية عليها
        watermark_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))

        # حساب عدد مرات تكرار العلامة المائية لتغطية الصورة بالكامل
        wm_width, wm_height = text_watermark.size
        cols = (base_image.width // wm_width) + 2
        rows = (base_image.height // wm_height) + 2

        # وضع العلامة المائية بشكل متكرر مع دوران وإزاحة عشوائية
        for i in range(-1, cols):
            for j in range(-1, rows):
                # إنشاء نسخة جديدة من العلامة المائية لكل تكرار
                wm_copy = text_watermark.copy()

                # تطبيق دوران عشوائي
                angle = random.randint(-45, 45)
                rotated_wm = wm_copy.rotate(angle, expand=True, resample=Image.BICUBIC)

                # حساب الموضع مع إزاحة عشوائية لجعل النمط أقل انتظاماً
                pos_x = i * wm_width + random.randint(-wm_width//4, wm_width//4)
                pos_y = j * wm_height + random.randint(-wm_height//4, wm_height//4)

                # لصق العلامة المائية في الطبقة الشفافة
                watermark_layer.paste(rotated_wm, (pos_x, pos_y), rotated_wm)

        # ضبط شفافية طبقة العلامات المائية باستخدام الثابت المحدد مسبقاً
        alpha = watermark_layer.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(WATERMARK_OPACITY)
        watermark_layer.putalpha(alpha)

        # دمج طبقة العلامات المائية مع الصورة الأصلية
        watermarked_image = Image.alpha_composite(base_image, watermark_layer)

        # حفظ الصورة النهائية بجودة عالية
        output_stream = io.BytesIO()
        watermarked_image.convert("RGB").save(output_stream, format='JPEG', quality=95)
        output_stream.seek(0)
        return output_stream

    except Exception as e:
        print(f"خطأ في دالة add_watermark: {e}")
        import traceback
        traceback.print_exc()
        return None


# --- معالجات أوامر البوت (Handlers) ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعرض رسالة الترحيب عند بدء استخدام البوت."""
    welcome_message = """
مرحباً بك في بوت حقوق "صياد العروض"! 📸

وظيفتي هي إضافة العلامة المائية "صياد العروض" على أي صورة ترسلها لي للحفاظ على حقوقك.

⚙️ **كيف تستخدم البوت؟**
1. أرسل صورة مباشرةً لوضع العلامة المائية عليها باللون الافتراضي (أسود).
2. استخدم الأمر /color لتغيير لون العلامة المائية.
3. استقبل صورتك مع العلامة المائية المضافة!

✨ **مميزات البوت:**
- دعم كامل للغة العربية.
- علامة مائية متعددة الألوان.
- جودة عالية للصور.
- سرعة في الأداء بفضل المعالجة غير المتزامنة.
"""
    await update.message.reply_text(welcome_message)


async def color_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعرض قائمة ألوان لاختيار لون العلامة المائية."""
    keyboard = [
        [
            InlineKeyboardButton("⚫️ أسود", callback_data='color_black'),
            InlineKeyboardButton("⚪️ أبيض", callback_data='color_white'),
            InlineKeyboardButton("🔴 أحمر", callback_data='color_red'),
        ],
        [
            InlineKeyboardButton("🔵 أزرق", callback_data='color_blue'),
            InlineKeyboardButton("🟢 أخضر", callback_data='color_green'),
            InlineKeyboardButton("🟠 برتقالي", callback_data='color_orange')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎨 اختر لون العلامة المائية:", reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج اختيار اللون من القائمة."""
    query = update.callback_query
    await query.answer() # مهم لإعلام تليجرام أن الزر تم التعامل معه

    color_map = {
        'color_black': {'name': 'الأسود', 'value': (0, 0, 0, 180)},
        'color_white': {'name': 'الأبيض', 'value': (255, 255, 255, 180)},
        'color_red': {'name': 'الأحمر', 'value': (200, 0, 0, 180)},
        'color_blue': {'name': 'الأزرق', 'value': (0, 0, 200, 180)},
        'color_green': {'name': 'الأخضر', 'value': (0, 128, 0, 180)},
        'color_orange': {'name': 'البرتقالي', 'value': (255, 140, 0, 180)}
    }

    choice = query.data
    if choice in color_map:
        selected_color = color_map[choice]
        context.user_data['font_color'] = selected_color['value']
        await query.edit_message_text(text=f"✅ تم اختيار اللون: {selected_color['name']}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج الصورة المرسلة من المستخدم ويضيف إليها العلامة المائية."""
    loading_msg = await update.message.reply_text("⏳ جاري معالجة الصورة، يرجى الانتظار...")

    try:
        font_color = context.user_data.get('font_color', DEFAULT_FONT_COLOR)

        # الحصول على الصورة بأعلى دقة متوفرة
        photo_file = await context.bot.get_file(update.message.photo[-1].file_id)
        input_stream = io.BytesIO()
        await photo_file.download_to_memory(input_stream)
        input_stream.seek(0)

        # [تحسين الأداء] تشغيل دالة معالجة الصورة في خيط منفصل
        # هذا يمنع البوت من "التجمد" أثناء معالجة الصور الكبيرة
        loop = asyncio.get_running_loop()
        watermarked_photo_stream = await loop.run_in_executor(
            None, add_watermark, input_stream, font_color
        )

        if watermarked_photo_stream:
            await update.message.reply_photo(
                photo=watermarked_photo_stream,
                caption="✅ تمت إضافة الحقوق بنجاح!\n@SayadAloroudh",
                filename="watermarked_by_SayadAloroudh.jpg"
            )
        else:
            await update.message.reply_text("❌ عذراً، حدث خطأ أثناء إضافة الحقوق. يرجى المحاولة لاحقاً.")

    except Exception as e:
        print(f"خطأ في معالج الصور الرئيسي handle_photo: {str(e)}")
        await update.message.reply_text("⚠️ حدث خطأ غير متوقع. يرجى إرسال صورة أخرى أو المحاولة لاحقاً.")
    finally:
        # حذف رسالة التحميل بعد الانتهاء
        await context.bot.delete_message(
            chat_id=update.message.chat_id,
            message_id=loading_msg.message_id
        )


# --- الدالة الرئيسية لتشغيل البوت ---
def main():
    """الدالة الرئيسية التي تقوم بإعداد وتشغيل البوت."""
    # فحص وجود التوكن قبل البدء
    if not TOKEN:
        print("="*50)
        print("خطأ فادح: لم يتم العثور على توكن البوت!")
        print("الرجاء تعيين متغير البيئة (Environment Variable) باسم TELEGRAM_TOKEN")
        print("="*50)
        sys.exit(1) # إيقاف البرنامج إذا لم يكن التوكن موجوداً

    # بدء خادم الويب في خيط منفصل
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("🚀 جارٍ تشغيل البوت...")

    # إعداد تطبيق البوت
    application = Application.builder().token(TOKEN).build()

    # إضافة معالجات الأوامر والرسائل
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", start_command)) # /help يعرض نفس رسالة البداية
    application.add_handler(CommandHandler("color", color_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # بدء استقبال التحديثات من تليجرام
    print("✅ البوت يعمل الآن وجاهز لاستقبال الصور.")
    application.run_polling()
    print("🛑 تم إيقاف البوت.")


if __name__ == '__main__':
    main()
