# Changelog

## 1.0.1

- Fix startup failure when the model download is interrupted.
- Download model archives to a temporary `.part` file and retry failed downloads.
- Remove incomplete model archives before retrying extraction.

## 1.0.0

- Initial release.
- Add Wyoming protocol Chinese ASR service using sherpa-onnx Paraformer.
- Use prebuilt multi-architecture Docker image.
