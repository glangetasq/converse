FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Shell form + exec so Cloud Run's ${PORT} expands and uvicorn is PID 1 (receives SIGTERM).
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}

