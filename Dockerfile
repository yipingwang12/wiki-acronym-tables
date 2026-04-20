FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY pwa/ pwa/
COPY configs/ configs/
COPY server.py .

RUN pip install --no-cache-dir -e ".[server]"

EXPOSE 8080

ENV DB_PATH=/data/quiz.db

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "120", "server:create_app()"]
