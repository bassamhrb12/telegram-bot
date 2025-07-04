# استخدام صورة أساسية خفيفة
FROM python:3.11-slim

# تثبيت حزم النظام المطلوبة
RUN apt-get update && apt-get install -y \
    libraqm0 \
    libfreetype6 \
    libharfbuzz0b \
    libfribidi0 \
    fonts-arabicttf \
    fonts-dejavu \
    ttf-mscorefonts-installer \
    fontconfig \
    locales \
    # تنظيف الذاكرة المؤقتة
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# تعيين بيئة اللغة العربية
RUN sed -i '/ar_AE.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen
ENV LANG ar_AE.UTF-8
ENV LC_ALL ar_AE.UTF-8

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
