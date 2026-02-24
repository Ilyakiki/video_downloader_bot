FROM python:3.12-slim

# Установка ffmpeg (нужен yt-dlp для слияния видео+аудио)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py config.py downloader.py handlers.py utils.py ./

# Папка для временных файлов
RUN mkdir -p downloads

CMD ["python", "bot.py"]
