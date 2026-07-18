FROM python:3.13-alpine@sha256:399babc8b49529dabfd9c922f2b5eea81d611e4512e3ed250d75bd2e7683f4b0

ARG BUILD_ARCH=unknown
ARG BUILD_VERSION=dev

LABEL \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="app" \
    io.hass.version="${BUILD_VERSION}" \
    org.opencontainers.image.description="DeepSeek to Ollama proxy for Home Assistant" \
    org.opencontainers.image.source="https://github.com/atsrxL/ha-addons"

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY app.py ./

EXPOSE 11435

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:11435/', timeout=3)" || exit 1

CMD ["python", "-u", "/app/app.py"]
