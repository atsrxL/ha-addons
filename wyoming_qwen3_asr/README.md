# Wyoming Qwen3 ASR

Higher-accuracy Chinese speech-to-text add-on for Home Assistant Assist.

This add-on runs a Wyoming protocol ASR service on port `10304`, backed by `Qwen/Qwen3-ASR-0.6B` on CPU.

Approx memory requirement: `4-6 GB`.

## Features

- Local Chinese / Mandarin speech recognition
- Wyoming protocol support for Home Assistant Assist
- Qwen3-ASR 0.6B CPU backend
- Prebuilt Docker image for `aarch64` and `amd64`
- Better recognition than Paraformer in previous tests, but slower and heavier

## Home Assistant

After starting the add-on, add a Wyoming Protocol integration:

```text
Host: Home Assistant host IP
Port: 10304
```

Then select this STT engine in your Assist pipeline.

## Model

The add-on downloads this model on first startup:

```text
Qwen/Qwen3-ASR-0.6B
```

The model is stored under the add-on config volume and is reused after restart.
