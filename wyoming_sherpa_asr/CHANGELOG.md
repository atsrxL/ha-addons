# Changelog

## 1.0.5

- Add safer model archive extraction.
- Pin Python package versions in the Docker image.
- Add `max_audio_seconds` to limit per-request audio memory use.
- Initialize logging before reading Home Assistant add-on options.
- Make the Docker base image configurable at build time.

## 1.0.4

- Remove the large Paraformer option and keep the fast int8 model only.
- Store downloaded model files under `/config/models` so add-on restarts reuse the cache.

## 1.0.3

- Add selectable Paraformer model option: `fast` or `large`.
- Add `num_threads` option.
- Add support for `sherpa-onnx-paraformer-zh-2024-03-09` large model.

## 1.0.2

- Add model download progress logs.
- Align the container port with the exposed default port `10303`.

## 1.0.1

- Fix startup failure when the model download is interrupted.
- Download model archives to a temporary `.part` file and retry failed downloads.
- Remove incomplete model archives before retrying extraction.

## 1.0.0

- Initial release.
- Add Wyoming protocol Chinese ASR service using sherpa-onnx Paraformer.
- Use prebuilt multi-architecture Docker image.
