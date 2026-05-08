FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg gcc \
    && rm -rf /var/lib/apt/lists/* \
    && pip install -r /app/requirements.txt

COPY app /app/app
COPY README.md /app/README.md
COPY docs /app/docs

CMD ["python", "-m", "app.main"]
