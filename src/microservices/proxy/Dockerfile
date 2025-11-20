# Используем официальный образ Python 3.11 slim
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей 
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код сервиса
COPY . .

# Открываем порт 8000
EXPOSE 8000

# Команда для запуска FastAPI с Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
