FROM python:3.12-slim
WORKDIR /app
# Patch OS-level packages (zlib, etc.) at build time rather than trusting
# the base image tag to already be current.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools && pip install --no-cache-dir -r requirements.txt \
    # Belt-and-braces cleanup of stale setuptools artifacts that `pip
    # install --upgrade setuptools` does not reliably remove, which Trivy
    # keeps flagging as the old vulnerable version regardless of the
    # upgrade above:
    #   1. ensurepip's own static bundled wheel (a file on disk, never
    #      touched by pip, and never needed again post-build)
    #   2. any leftover setuptools .dist-info/.egg-info directory that
    #      does not match the version actually now installed (the base
    #      image's original install isn't always fully replaced by an
    #      upgrade in the same site-packages tree)
    && rm -rf /usr/local/lib/python3.12/ensurepip/_bundled \
    && INSTALLED_SETUPTOOLS=$(python3 -c "import setuptools; print(setuptools.__version__)") \
    && find / -xdev -depth \( -iname "setuptools-*.dist-info" -o -iname "setuptools-*.egg-info" -o -iname "setuptools.egg-info" \) \
         ! -iname "setuptools-${INSTALLED_SETUPTOOLS}*" -exec rm -rf {} + 2>/dev/null || true
COPY app ./app
COPY static ./static
ENV MAIL_DB_PATH=/data/mail.db
EXPOSE 8004
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
