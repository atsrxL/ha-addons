# Documentation

## Usage

Start the add-on from Home Assistant. On first startup it downloads the Paraformer Chinese model. This can take a few minutes depending on network speed.

The Wyoming protocol service listens on port `10303`. The add-on exposes the same port on the host by default.

## Assist Pipeline

1. Go to **Settings > Devices & services**.
2. Add the **Wyoming Protocol** integration.
3. Use the Home Assistant host IP as the host.
4. Use port `10303`.
5. Select the new STT engine in your Assist pipeline.

## Container Image

This add-on uses the GitHub Container Registry image:

```text
ghcr.io/atsrxl/wyoming-sherpa-asr:latest
```

The image is multi-architecture and supports:

```text
linux/amd64
linux/arm64
```

Version `1.0.6` is a registry migration of the existing Docker Hub `1.0.5` image. The application contents are unchanged.

## Notes

- Language: Chinese / Mandarin
- Backend: `sherpa-onnx`
- Model: `sherpa-onnx-paraformer-zh-2023-09-14`
- Model cache: `/config/models`
- Approx memory: `0.5-1 GB`
- Max audio duration: configurable, default `120` seconds
- Internal port: `10303`
- Default exposed port: `10303`