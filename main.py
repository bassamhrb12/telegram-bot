import os
import io
import threading
import random
import sys
import locale
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

# --- ضبط بيئة اللغة العربية ---
os.environ["LANG"] = "ar_AE.UTF-8"
os.environ["LC_ALL"] = "ar_AE.UTF-8"
try:
    locale.setlocale(locale.LC_ALL, 'ar_AE.UTF-8')
except locale.Error:
    print("Warning: Arabic locale not available, using default")

# --- الإعدادات الرئيسية ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
WATERMARK_TEXT = "صياد العروض"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "fonts", "Amiri-Bold.ttf")  # خط عربي ثقيل
FONT_SIZE = 60
DEFAULT_FONT_COLOR = (0, 0, 0, 180)  # أسود مع شفافية
BACKGROUND_COLOR = (255, 255, 255, 0)  # خلفية شفافة
TEXT_OUTLINE_COLOR = (255, 255, 255, 200)  # لون الحد الأبيض

# --- خادم الويب ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# --- دالة إنشاء علامة مائية نصية ---
def create_text_watermark(text, font_path, font_size, font_color, outline_color):
    """إنشاء صورة شفافة تحتوي على النص العربي"""
    # معالجة النص العربي
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    
    # تحميل الخط
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        # استخدام خط احتياطي إذا فشل
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()
    
    # حساب حجم النص
    temp_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    text_bbox = temp_draw.textbbox((0, 0), bidi_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    # إنشاء صورة شفافة بحجم النص
    watermark = Image.new('RGBA', (int(text_width * 1.2), int(text_height * 1.5)), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(watermark)
    
    # إضافة تأثير الظل (الحد الأبيض)
    outline_positions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    for dx, dy in outline_positions:
        draw.text(
            ((watermark.width - text_width) // 2 + dx, 
             (watermark.height - text_height) // 2 + dy),
            bidi_text, 
            font=font, 
            fill=outline_color
        )
    
    # إضافة النص الرئيسي
    draw.text(
        ((watermark.width - text_width) // 2, 
         (watermark.height - text_height) // 2),
        bidi_text, 
        font=font, 
        fill=font_color
    )
    
    # تطبيق تأثير ضبابي خفيف للحواف
    watermark = watermark.filter(ImageFilter.GaussianBlur(radius=1))
    
    return watermark

# --- دالة إضافة العلامة المائية إلى الصورة ---
def add_watermark(input_image_stream, font_color):
    try:
        # فتح الصورة الأساسية
        base_image = Image.open(input_image_stream).convert("RGBA")
        
        # إنشاء العلامة المائية النصية
        text_watermark = create_text_watermark(
            WATERMARK_TEXT,
            FONT_PATH,
            FONT_SIZE,
            font_color,
            TEXT_OUTLINE_COLOR
        )
        
        # إنشاء طبقة شفافة بنفس حجم الصورة الأصلية
        watermark_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
        
        # حساب عدد المرات لتكرار العلامة المائية
        wm_width, wm_height = text_watermark.size
        cols = base_image.width // wm_width + 1
        rows = base_image.height // wm_height + 1
        
        # وضع العلامة المائية بشكل متكرر مع دوران عشوائي
        for i in range(cols):
            for j in range(rows):
                # إنشاء نسخة من العلامة المائية
                wm_copy = text_watermark.copy()
                
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
        alpha = ImageEnhance.Brightness(alpha).enhance(0.6)  # 60% شفافية
        watermark_layer.putalpha(alpha)
        
        # دمج الصور
        watermarked_image = Image.alpha_composite(base_image, watermark_layer)
        
        # تحويل الصورة الناتجة
        output_stream = io.BytesIO()
        watermarked_image.convert("RGB").save(output_stream, format='JPEG', quality=95)
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
            InlineKeyboardButton("🔵 أزرق", callback_data='color_blue'),
            InlineKeyboardButton("🟢 أخضر", callback_data='color_green')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر لون العلامة المائية:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    color_map = {
        'color_black': {'name': 'الأسود', 'value': (0, 0, 0, 180)},
        'color_red': {'name': 'الأحمر', 'value': (255, 0, 0, 180)},
        'color_blue': {'name': 'الأزرق', 'value': (0, 0, 255, 180)},
        'color_green': {'name': 'الأخضر', 'value': (0, 128, 0, 180)}
    }

    choice = query.data
    if choice in color_map:
        selected_color = color_map[choice]
        context.user_data['font_color'] = selected_color['value']
        await query.edit_message_text(text=f"✅ تم اختيار اللون: {selected_color['name']}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loading_msg = await update.message.reply_text("⏳ جاري معالجة الصورة، يرجى الانتظار...")
    
    try:
        font_color = context.user_data.get('font_color', DEFAULT_FONT_COLOR)
        
        photo_file = await context.bot.get_file(update.message.photo[-1].file_id)
        input_stream = io.BytesIO()
        await photo_file.download_to_memory(input_stream)
        input_stream.seek(0)

        watermarked_photo_stream = add_watermark(input_stream, font_color)

        if watermarked_photo_stream:
            await update.message.reply_photo(
                photo=watermarked_photo_stream, 
                caption="✅ تمت إضافة الحقوق بنجاح!",
                filename="watermarked.jpg"
            )
        else:
            await update.message.reply_text("❌ عذراً، حدث خطأ أثناء إضافة الحقوق.")
    except Exception as e:
        print(f"Error handling photo: {e}")
        await update.message.reply_text("⚠️ حدث خطأ غير متوقع أثناء المعالجة.")
    finally:
        # حذف رسالة التحميل
        try:
            await context.bot.delete_message(
                chat_id=update.message.chat_id,
                message_id=loading_msg.message_id
            )
        except:
            pass

# --- الدالة الرئيسية لتشغيل البوت ---
def main():
    if not TOKEN:
        print("Fatal Error: TELEGRAM_TOKEN not found.")
        return

    # بدء خادم الويب في خيط منفصل
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Bot is running...")
    application = Application.builder().token(TOKEN).build()

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("color", color_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # بدء استقبال التحديثات
    application.run_polling()

if __name__ == '__main__':
    main()
