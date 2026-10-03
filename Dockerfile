FROM node:22-alpine AS frontend-builder

WORKDIR /build/front
COPY front/package*.json ./
RUN npm ci
COPY front/ ./
RUN npm run build

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MONITORAPET_DATA_DIR=/data

WORKDIR /app

COPY back/requirements.txt ./back/requirements.txt
RUN pip install --no-cache-dir -r back/requirements.txt

COPY back/ ./back/
COPY --from=frontend-builder /build/front/dist ./front/dist/

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/api/health', timeout=3)" || exit 1

CMD ["sh", "-c", "python -m app.infra.ai.model_setup && exec uvicorn app.main:app --app-dir back --host 0.0.0.0 --port 8000"]
