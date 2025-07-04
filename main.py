import os
import io
import threading
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
from PIL import Image, ImageDraw, ImageFont
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

# تحديد مسار الخط بشكل مطلق
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "fonts", "Amiri-Regular.ttf")
FONT_SIZE = 35
DEFAULT_FONT_COLOR = (0, 0, 0, 128)  # اللون الافتراضي أسود

# --- خادم الويب ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# --- دالة إضافة العلامة المائية ---
def add_watermark(input_image_stream, font_color):
    try:
        # تحميل الصورة
        image = Image.open(input_image_stream).convert("RGBA")
        txt_layer = Image.new("RGBA", image.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt_layer)

        # معالجة النص العربي
   reshaped_text = arabic_reshaper.reshape(WATERMARK_TEXT)
        bidi_text = get_display(reshaped_text)

        # تحميل الخط العربي
      try:
            font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        except IOError:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", FONT_SIZE)
            except:
                try:
                    font = ImageFont.truetype("arial.ttf", FONT_SIZE)
                except:
                    font = ImageFont.load_default()
        # حساب حجم النص
        text_bbox = draw.textbbox((0, 0), bidi_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # إعداد الخطوة للعلامات المائية
        x_step = int(text_width * 1.8)
        y_step = int(text_height * 3)
        angle = 30  # زاوية الميل

        # إضافة علامات مائية متعددة بزاوية
        for x in range(-image.width, image.width, x_step):
            for y in range(-image.height, image.height, y_step):
                # إنشاء طبقة نصية مؤقتة
                txt_temp = Image.new("RGBA", image.size, (255, 255, 255, 0))
                draw_temp = ImageDraw.Draw(txt_temp)
                
                # إضافة النص
                draw_temp.text(
                    (x, y), 
                    bidi_text, 
                    font=font, 
                    fill=font_color,
                    stroke_width=1,
                    stroke_fill=(255, 255, 255, 100)
                )
                
                # تطبيق الدوران
                txt_temp = txt_temp.rotate(angle, expand=0, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))
                
                # دمج مع الطبقة الرئيسية
                txt_layer = Image.alpha_composite(txt_layer, txt_temp)

        # دمج الصورة مع العلامة المائية
        watermarked_image = Image.alpha_composite(image, txt_layer)
        
        # حفظ الصورة الناتجة
        output_stream = io.BytesIO()
      
