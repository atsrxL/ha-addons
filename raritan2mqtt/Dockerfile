ARG BUILD_ARCH
FROM ghcr.io/home-assistant/${BUILD_ARCH}-base:3.21

ARG BUILD_VERSION
ARG BUILD_ARCH

LABEL \
  io.hass.name="Raritan PX MQTT" \
  io.hass.description="Raritan PX2/PX3 JSON-RPC to MQTT Discovery bridge" \
  io.hass.type="addon" \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache \
      ca-certificates \
      python3 \
      py3-pip \
    && python3 -m pip install --no-cache-dir --break-system-packages \
      paho-mqtt==2.1.0 \
      raritan==3.6.0.46486

COPY run.sh /run.sh
COPY app /app

RUN chmod a+x /run.sh

CMD ["/run.sh"]
