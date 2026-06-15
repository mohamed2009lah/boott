FROM python:3.11-slim

# تثبيت الاعتماديات الأساسية
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    ffmpeg \
    wget \
    && rm -rf /var/lib/apt/lists/*

# تحميل بيانات Tesseract للعربية
RUN mkdir -p /usr/share/tesseract-ocr/4.00/tessdata/ && \
    wget -O /usr/share/tesseract-ocr/4.00/tessdata/ara.traineddata \
    https://github.com/tesseract-ocr/tessdata/raw/main/ara.traineddata

WORKDIR /app

# نسخ الملفات أولاً
COPY requirements.txt .

# تثبيت المكتبات
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي الملفات
COPY . .

# التحقق من التثبيت
RUN python -c "from telegram import Bot; print('✅ python-telegram-bot installed successfully')"

# تشغيل البوت
CMD ["python", "main.py"]
