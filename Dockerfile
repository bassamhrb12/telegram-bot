FROM python:3.10-slim

# تثبيت حزم الخطوط العربية والاعتماديات
RUN apt-get update && apt-get install -y \
    fonts-arabicttf \
    fonts-dejavu \
    ttf-mscorefonts-installer \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# إنشاء مجلد العمل
WORKDIR /app

# نسخ ملفات المشروع
COPY . .

# تثبيت المكتبات
RUN pip install --no-cache-dir -r requirements.txt

# تحديث ذاكرة الخطوط
RUN fc-cache -fv

# تشغيل البوت
CMD ["python", "main.py"]
