FROM python:3.12-slim
WORKDIR /app
# Patch OS-level packages (zlib, etc.) at build time rather than trusting
# the base image tag to already be current.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools && pip install --no-cache-dir -r requirements.txt \
    # ensurepip ships a static, unused bundled setuptools wheel under
    # /usr/local/lib/python3.12/ensurepip/_bundled/ that `pip install
    # --upgrade setuptools` never touches (it's a file on disk, not an
    # installed package) -- Trivy flags that stale copy regardless. We
    # never run ensurepip again after this point, so delete it.
    && rm -rf /usr/local/lib/python3.12/ensurepip/_bundled
COPY app ./app
COPY static ./static
ENV DOCS_DB_PATH=/data/docs.db
EXPOSE 8003
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
