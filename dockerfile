FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    ffmpeg \
    wget \
    && rm -rf /var/lib/apt/lists/*

# تأكد من وجود ملفات اللغة العربية (إذا لم تكن موجودة)
RUN if [ ! -f /usr/share/tesseract-ocr/5/tessdata/ara.traineddata ]; then \
        wget -P /usr/share/tesseract-ocr/5/tessdata/ https://github.com/tesseract-ocr/tessdata/raw/main/ara.traineddata; \
    fi

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "main.py"]