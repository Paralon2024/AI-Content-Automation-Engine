#!/bin/bash
set -e

MODEL_PATH="${WHISPER_MODEL_PATH:-/opt/whisper/ggml-small.bin}"

if [ ! -f "$MODEL_PATH" ]; then
    echo "📥 Downloading Whisper model (~150 MB)..."
    mkdir -p "$(dirname "$MODEL_PATH")"
    curl -L --retry 5 --retry-delay 5 --progress-bar \
        -o "$MODEL_PATH" \
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"
    echo "✅ Model downloaded to $MODEL_PATH"
else
    echo "✅ Whisper model found at $MODEL_PATH"
fi

exec "$@"
