# PaperTrail backend (FastAPI). Stable Python (the local dev venv uses 3.14;
# the image pins 3.12 for broad wheel availability of the pinned deps).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: build tools for any sdists, plus a MySQL client lib if needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt

COPY . .

# gunicorn with uvicorn workers for a production process manager. Workers are
# stateless; shared state lives in MySQL and Redis (see DEPLOYMENT.md).
RUN pip install "gunicorn==23.0.0"

EXPOSE 8000

# Apply migrations, then serve. WEB_CONCURRENCY controls worker count.
CMD ["sh", "-c", "alembic upgrade head && gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-4} -b 0.0.0.0:${PORT:-8000} --access-logfile -"]
