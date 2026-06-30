# Documentation

## Usage

Start the add-on from Home Assistant. On first startup it downloads Qwen3-ASR 0.6B from Hugging Face. This can take a while depending on network speed. The log prints the Hugging Face cache path and when model files are ready.

The Wyoming protocol service listens on port `10304`. The add-on exposes the same port on the host by default.

## Assist Pipeline

1. Go to **Settings > Devices & services**.
2. Add the **Wyoming Protocol** integration.
3. Use the Home Assistant host IP as the host.
4. Use port `10304`.
5. Select the new STT engine in your Assist pipeline.

## Docker Image

This add-on uses:

```text
atsrxl/wyoming-qwen3-asr:latest
```

The `latest` tag is multi-architecture and supports:

```text
linux/amd64
linux/arm64
```

## Notes

- Language: Chinese / Mandarin
- Backend: `qwen-asr` with CPU PyTorch
- Model: `Qwen/Qwen3-ASR-0.6B`
- Model cache: `/config/hf`
- Approx memory: `4-6 GB`
- Internal port: `10304`
- Default exposed port: `10304`
- This is more accurate than Paraformer in previous tests, but noticeably slower and much larger.
