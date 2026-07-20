FROM ghcr.io/home-assistant/base:3.23

ARG BUILD_ARCH=unknown
ARG BUILD_VERSION=dev

LABEL \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="app" \
    io.hass.version="${BUILD_VERSION}" \
    org.opencontainers.image.title="Home Assistant App: UPS NUT Server" \
    org.opencontainers.image.description="Network UPS Tools server for USB and serial UPS devices" \
    org.opencontainers.image.source="https://github.com/atsrxL/ha-addons" \
    org.opencontainers.image.licenses="GPL-2.0-or-later"

RUN apk add --no-cache \
        nut \
        nut-udev \
        usbutils

ENV NUT_CONFPATH=/etc/nut \
    NUT_STATEPATH=/run/nut \
    NUT_ALTPIDPATH=/run/nut \
    NUT_QUIET_INIT_UPSNOTIFY=true \
    NUT_QUIET_INIT_NDE_WARNING=true

COPY run.sh /run.sh
RUN chmod 0755 /run.sh

EXPOSE 3493

CMD ["/run.sh"]
