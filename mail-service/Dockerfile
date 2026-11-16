FROM python:3.12-slim
WORKDIR /app
# Patch OS-level packages (zlib, etc.) at build time rather than trusting
# the base image tag to already be current.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static
ENV MAIL_DB_PATH=/data/mail.db
EXPOSE 8004
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
