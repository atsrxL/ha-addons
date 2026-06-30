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
- Approx memory: `0.5-1 GB`
- Internal port: `10303`
- Default exposed port: `10303`
