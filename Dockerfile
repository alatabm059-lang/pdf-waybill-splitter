FROM python:3.11-slim

# تثبيت Tesseract OCR والمكتبات المطلوبة
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libpoppler-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# نسخ ملفات المشروع
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# تشغيل البرنامج
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
