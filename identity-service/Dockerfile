FROM python:3.12-slim AS builder
WORKDIR /app
# Patch OS-level packages (zlib, etc.) at build time rather than trusting
# the base image tag to already be current.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools && pip install --no-cache-dir -r requirements.txt \
    # pip and setuptools are only needed to install the app's dependencies,
    # never at runtime. Removing them (and, critically, pip's own *vendored*
    # internal copy of pkg_resources/setuptools, which ships bundled inside
    # pip's own package directory regardless of the top-level setuptools
    # version) from the venv before it's copied into the final image is what
    # actually eliminates CVE-2025-47273 — deleting/upgrading the top-level
    # setuptools install alone does not touch this vendored copy, which is
    # what a vulnerability scanner keeps detecting as "setuptools 70.3.0"
    # even when the real installed setuptools is current.
    && find /opt/venv/lib/python3.12/site-packages -maxdepth 1 \
         \( -iname "pip" -o -iname "pip-*.dist-info" \
            -o -iname "setuptools" -o -iname "setuptools-*.dist-info" \
            -o -iname "wheel" -o -iname "wheel-*.dist-info" \) \
         -exec rm -rf {} +

FROM python:3.12-slim
WORKDIR /app
# Same OS-level patching as the builder stage, applied again since this is a
# fresh FROM — and strip the base image's own pre-installed pip/setuptools
# (and their bundled ensurepip wheels) from the runtime image too, since
# nothing at runtime needs them and they carry the same vendored-pkg_resources
# issue described above.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.12/ensurepip \
    && find /usr/local/lib/python3.12/site-packages -maxdepth 1 \
         \( -iname "pip" -o -iname "pip-*.dist-info" \
            -o -iname "setuptools" -o -iname "setuptools-*.dist-info" \
            -o -iname "wheel" -o -iname "wheel-*.dist-info" \) \
         -exec rm -rf {} +
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY app ./app
ENV IDENTITY_DB_PATH=/data/identity.db
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
