# Wyoming Sherpa ASR

Chinese speech-to-text add-on for Home Assistant Assist.

This add-on runs a Wyoming protocol ASR service on port `10303`, backed by `sherpa-onnx` and selectable Paraformer Chinese models.

Approx memory requirement:

- `fast`: `0.5-1 GB`
- `large`: `1.5-2.5 GB`

## Features

- Local Chinese / Mandarin speech recognition
- Wyoming protocol support for Home Assistant Assist
- Prebuilt Docker image for `aarch64` and `amd64`
- Suitable for Raspberry Pi 5 and other ARM64 hosts
- Fast response for Home Assistant voice control

## Options

- `model`: `fast` or `large`
- `num_threads`: CPU worker threads, default `4`

## Home Assistant

After starting the add-on, add a Wyoming Protocol integration:

```text
Host: Home Assistant host IP
Port: 10303
```

Then select this STT engine in your Assist pipeline.

## Model

The add-on downloads the selected model on first startup:

```text
fast:  sherpa-onnx-paraformer-zh-2023-09-14
large: sherpa-onnx-paraformer-zh-2024-03-09
```

The model is stored under the add-on config volume and is reused after restart.
