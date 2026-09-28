FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
RUN pip install --no-cache-dir .

COPY scripts ./scripts
RUN mkdir -p /app/output /app/secrets

CMD ["python", "-m", "grume.worker", "loop", "--interval", "60"]
