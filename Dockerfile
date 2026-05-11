FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-rus \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY src/ ./src/
COPY data/references/ ./data/references/
COPY entrypoint.sh .

RUN mkdir -p /app/references.bundled && \
    cp -r /app/data/references/* /app/references.bundled/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-m", "legal_claim_assistant", "serve", "--host", "0.0.0.0", "--port", "8000"]
