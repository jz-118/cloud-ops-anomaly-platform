FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
RUN useradd --system --uid 10001 app
USER 10001

ENV PYTHONPATH=/app/src
EXPOSE 8080
CMD ["python", "-m", "demo_app.main"]

