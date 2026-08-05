FROM ghcr.io/home-assistant/base:3.23

ARG BUILD_ARCH=unknown
ARG BUILD_VERSION=dev

LABEL \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="app" \
    io.hass.version="${BUILD_VERSION}" \
    org.opencontainers.image.title="Home Assistant App: Mercury PoE MQTT" \
    org.opencontainers.image.description="Mercury managed PoE switch to MQTT Discovery bridge" \
    org.opencontainers.image.source="https://github.com/atsrxL/ha-addons" \
    org.opencontainers.image.licenses="MIT"

RUN apk add --no-cache \
        ca-certificates \
        python3 \
        py3-pip \
    && python3 -m pip install \
        --break-system-packages \
        --no-cache-dir \
        paho-mqtt==2.1.0

COPY run.sh /run.sh
COPY app /app

RUN chmod 0755 /run.sh

CMD ["/run.sh"]
