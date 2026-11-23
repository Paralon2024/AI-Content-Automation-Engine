#!/bin/bash
set -e

MODEL_PATH="${WHISPER_MODEL_PATH:-/opt/whisper/ggml-small.bin}"
TEMP_PATH="${MODEL_PATH}.download"

if [ ! -s "$MODEL_PATH" ]; then
    echo "📥 Downloading Whisper small model (~466 MB)..."
    mkdir -p "$(dirname "$MODEL_PATH")"
    rm -f "$TEMP_PATH"
    curl -fL --retry 5 --retry-delay 5 --progress-bar \
        -o "$TEMP_PATH" \
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"
    test -s "$TEMP_PATH"
    mv "$TEMP_PATH" "$MODEL_PATH"
    echo "✅ Model downloaded to $MODEL_PATH"
else
    echo "✅ Whisper model found at $MODEL_PATH"
fi

exec "$@"
