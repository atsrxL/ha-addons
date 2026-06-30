# Documentation

## Usage

Start the add-on from Home Assistant. On first startup it downloads the Paraformer Chinese model. This can take a few minutes depending on network speed.

The Wyoming protocol service listens inside the container on port `10300`. The add-on exposes it on host port `10303` by default.

## Assist Pipeline

1. Go to **Settings > Devices & services**.
2. Add the **Wyoming Protocol** integration.
3. Use the Home Assistant host IP as the host.
4. Use port `10303`.
5. Select the new STT engine in your Assist pipeline.

## Docker Image

This add-on uses:

```text
atsrxl/wyoming-sherpa-asr:latest
```

The `latest` tag is multi-architecture and supports:

```text
linux/amd64
linux/arm64
```

## Notes

- Language: Chinese / Mandarin
- Backend: `sherpa-onnx`
- Model: `sherpa-onnx-paraformer-zh-2023-09-14`
- Internal port: `10300`
- Default exposed port: `10303`

