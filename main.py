import os
import io
import threading
import random
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
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# --- الإعدادات الرئيسية ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
WATERMARKS_DIR = os.path.join(os.path.dirname(__file__), "watermarks")
DEFAULT_OPACITY = 0.6  # شفافية افتراضية 60%

# --- خادم الويب ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# --- دالة إضافة العلامة المائية باستخدام صورة مسبقة الصنع ---
def add_watermark(input_image_stream, color_name):
    try:
        # فتح الصورة الأساسية
        base_image = Image.open(input_image_stream).convert("RGBA")
        
        # تحميل العلامة المائية المناسبة للون
        watermark_path = os.path.join(WATERMARKS_DIR, f"{color_name}.png")
        watermark = Image.open(watermark_path).convert("RGBA")
        
        # تغيير حجم العلامة المائية لتتناسب مع الصورة
        wm_size = (base_image.width // 3, base_image.height // 8)
        watermark = watermark.resize(wm_size, Image.LANCZOS)
        
        # إنشاء طبقة شفافة بنفس حجم الصورة الأصلية
        watermark_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        
        # حساب عدد المرات لتكرار العلامة المائية
        wm_width, wm_height = watermark.size
        cols = base_image.width // wm_width + 1
        rows = base_image.height // wm_height + 1
        
        # وضع العلامة المائية بشكل متكرر مع دوران عشوائي
        for i in range(cols):
            for j in range(rows):
                # إنشاء نسخة من العلامة المائية
                wm_copy = watermark.copy()
                
                # تطبيق دوران عشوائي
                angle = random.randint(-30, 30)
                rotated_wm = wm_copy.rotate(angle, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))
                
                # حساب الموضع مع إزاحة عشوائية
                x = i * wm_width + random.randint(-50, 50)
                y = j * wm_height + random.randint(-50, 50)
                
                # لصق العلامة المائية في الطبقة
                watermark_layer.paste(rotated_wm, (x, y), rotated_wm)
        
        # ضبط شفافية الطبقة
        alpha = watermark_layer.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(DEFAULT_OPACITY)
        watermark_layer.putalpha(alpha)
        
        # دمج الصور
        watermarked_image = Image.alpha_composite(base_image, watermark_layer)
        
        # تحويل الصورة الناتجة
        output_stream = io.BytesIO()
        watermarked_image.convert("RGB").save(output_stream, format='JPEG', quality=90)
        output_stream.seek(0)
        return output_stream
    except Exception as e:
        print(f"Error processing image: {e}")
        import traceback
        traceback.print_exc()
        return None

# --- معالجات أوامر البوت ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = """
مرحباً بك في بوت حقوق "صياد العروض"! 📸

وظيفتي هي إضافة العلامة المائية "صياد العروض" على أي صورة ترسلها لي للحفاظ على حقوقك.

**كيف تستخدم البوت؟**
- أرسل صورة مباشرةً لوضع العلامة المائية عليها باللون الافتراضي (أسود).
- لتغيير لون العلامة المائية، استخدم الأمر /color.
"""
    await update.message.reply_text(welcome_message)

async def color_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    query = update.callback_query
    await query.answer()

    color_map = {
        'color_black': 'black',
        'color_red': 'red',
        'color_blue': 'blue',
    }

    choice = query.data
    if choice in color_map:
        context.user_data['watermark_color'] = color_map[choice]
        color_names = {'black': 'الأسود', 'red': 'الأحمر', 'blue': 'الأزرق'}
        await query.edit_message_text(text=f"✅ تم اختيار اللون: {color_names[color_map[choice]]}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("جاري معالجة الصورة، يرجى الانتظار...")
    try:
        color_name = context.user_data.get('watermark_color', 'black')
        
        photo_file = await context.bot.get_file(update.message.photo[-1].file_id)
        input_stream = io.BytesIO()
        await photo_file.download_to_memory(input_stream)
        input_stream.seek(0)

        watermarked_photo_stream = add_watermark(input_stream, color_name)

        if watermarked_photo_stream:
            await update.message.reply_photo(photo=watermarked_photo_stream, caption="تمت إضافة الحقوق بنجاح!")
        else:
            await update.message.reply_text("عذراً، حدث خطأ أثناء إضافة الحقوق.")
    except Exception as e:
        print(f"Error handling photo: {e}")
        await update.message.reply_text("حدث خطأ غير متوقع.")

# --- الدالة الرئيسية لتشغيل البوت ---
def main():
    if not TOKEN:
        print("Fatal Error: TELEGRAM_TOKEN not found.")
        return

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    print("Bot is running...")
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("color", color_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    application.run_polling()

if __name__ == '__main__':
    main()
