# Changelog

## 1.0.1

- Add explicit startup logs for Qwen model download/cache and CPU initialization.
- Store Hugging Face model cache under `/config/hf`.
- Remove deprecated `TRANSFORMERS_CACHE` environment variable.

## 1.0.0

- Initial release of Wyoming Qwen3 ASR add-on.
- Uses `Qwen/Qwen3-ASR-0.6B` with CPU backend.
- Exposes Wyoming protocol on port `10304`.
