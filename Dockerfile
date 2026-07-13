FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for psycopg2 build (runtime uses psycopg2-binary, but keep libpq present).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000 8501

# Default to the FastAPI service; docker-compose overrides the command per service.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
