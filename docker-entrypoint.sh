#!/bin/sh
set -eu

MODEL_PATH="${WHISPER_MODEL_PATH:-/opt/whisper/ggml-small.bin}"
TEMP_PATH="${MODEL_PATH}.download"

if [ ! -s "$MODEL_PATH" ]; then
    echo "Downloading Whisper small model (~466 MB)..."
    mkdir -p "$(dirname "$MODEL_PATH")"
    rm -f "$TEMP_PATH"

    if ! curl -fL --retry 5 --retry-delay 5 --retry-all-errors --progress-bar \
        -o "$TEMP_PATH" \
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"; then
        rm -f "$TEMP_PATH"
        echo "ERROR: Whisper model download failed." >&2
        exit 1
    fi

    if [ ! -s "$TEMP_PATH" ]; then
        rm -f "$TEMP_PATH"
        echo "ERROR: Whisper model download produced an empty file." >&2
        exit 1
    fi

    mv "$TEMP_PATH" "$MODEL_PATH"
    echo "Whisper model downloaded to $MODEL_PATH"
else
    echo "Whisper model found at $MODEL_PATH"
fi

exec "$@"
