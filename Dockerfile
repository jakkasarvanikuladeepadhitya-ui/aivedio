# ---------- 1. build the React frontend ----------
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2. API + built UI on one port ----------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
RUN apt-get update  && apt-get install -y --no-install-recommends ffmpeg espeak-ng ca-certificates  && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY backend/ backend/
COPY --from=frontend /fe/dist frontend/dist

# Build-time checks: fail the build (not the first user request) if something is missing.
RUN ffmpeg -version | head -1 && ffprobe -version | head -1  && python -c "import fastapi, uvicorn, pydantic, httpx, dotenv, multipart, gradio_client; print('imports ok')"  && cd backend && python -c "import app.main"  && test -f /app/frontend/dist/index.html

# Defaults that make sense on Render (no GPU, no Ollama). HF_TOKEN / HF_SPACES come from the Render dashboard.
ENV STORAGE_DIR=/app/storage     VIDEO_PROVIDER=hf_space     STORYBOARD_ENGINE=rules     NARRATION_ENGINE=espeak     HW_ENCODE=off
RUN mkdir -p /app/storage/uploads /app/storage/clips /app/storage/audio /app/storage/exports  && useradd --create-home app && chown -R app:app /app/storage
USER app

WORKDIR /app/backend
EXPOSE 8000
# Render sets $PORT; locally it falls back to 8000. Must listen on 0.0.0.0.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
