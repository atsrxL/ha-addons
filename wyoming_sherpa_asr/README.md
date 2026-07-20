# Wyoming Sherpa ASR

Chinese speech-to-text add-on for Home Assistant Assist.

This add-on runs a Wyoming protocol ASR service on port `10303`, backed by `sherpa-onnx` and the Paraformer Chinese int8 model.

Approx memory requirement: `0.5-1 GB`.

## Features

- Local Chinese / Mandarin speech recognition
- Wyoming protocol support for Home Assistant Assist
- Prebuilt GHCR image for `aarch64` and `amd64`
- Suitable for Raspberry Pi 5 and other ARM64 hosts
- Fast response for Home Assistant voice control

## Options

- `num_threads`: CPU worker threads, default `4`
- `max_audio_seconds`: maximum accepted audio duration, default `120`

## Home Assistant

After starting the add-on, add a Wyoming Protocol integration:

```text
Host: Home Assistant host IP
Port: 10303
```

Then select this STT engine in your Assist pipeline.

## Image

```text
ghcr.io/atsrxl/wyoming-sherpa-asr
```

## Model

The add-on downloads this model on first startup:

```text
sherpa-onnx-paraformer-zh-2023-09-14
```

The model is stored under `/config/models` in the add-on config volume and is reused after restart.