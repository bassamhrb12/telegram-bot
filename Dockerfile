# 1. تحديد بيئة بايثون الأساسية
FROM python:3.11-slim

# 2. تثبيت مكتبة اللغة العربية الضرورية للنظام
RUN apt-get update && apt-get install -y libraqm0

# 3. تجهيز مجلد العمل داخل البيئة
WORKDIR /app

# 4. نسخ ملف المكتبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. نسخ جميع ملفات المشروع الأخرى
COPY . .

# 6. تحديد الأمر النهائي لتشغيل البوت
CMD ["python", "main.py"]
