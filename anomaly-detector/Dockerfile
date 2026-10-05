FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src

RUN useradd --system --uid 10001 --create-home detector \
    && mkdir -p /var/lib/anomaly-detector \
    && chown -R detector:detector /var/lib/anomaly-detector
USER 10001

ENV PYTHONPATH=/app/src \
    MODEL_DIR=/var/lib/anomaly-detector
EXPOSE 8080
CMD ["python", "-m", "anomaly_detector.main"]

