# AI Content Automation Engine

A modular, local-first application for creating short-form videos with AI-assisted scripts, voiceovers, subtitles, music, and FFmpeg-based assembly.

The project uses a **Tools & Pipelines** architecture: reusable integrations live in `tools/`, while the content-generation workflow lives in `flows/`.

## Features

- Generate structured video scripts with Google Gemini.
- Generate English voiceovers with Gemini text-to-speech.
- Upload and organize MP4 scene clips.
- Synchronize scene videos with generated narration.
- Generate subtitles locally with Whisper.cpp.
- Manage background music and mix it into the final video.
- Assemble and download the finished MP4.

> **Current workflow note:** The web application currently expects scene videos to be uploaded by the user. The image-generation, Midjourney/Discord, and Gemini video-generation modules are separate integrations and are not yet connected to the main web workflow. The Gemini video module now uses the Gemini Omni Interactions API and requires a billed Tier 1 Gemini API project.

## Requirements

- Docker Engine
- Docker Compose v2
- A Google Gemini API key

No local Python, Node.js, FFmpeg, or Whisper installation is required when using Docker Compose.

## Quick start

1. Clone this repository:

   ```bash
   git clone https://github.com/Paralon2024/AI-Content-Automation-Engine.git
   cd AI-Content-Automation-Engine
   ```

2. Build and start the application:

   ```bash
   docker compose up --build
   ```

3. Open the web application:

   - Frontend: http://localhost:5678
   - Backend API: http://localhost:8000
   - Health check: http://localhost:8000/api/health

4. In the application, open **Gemini Key** and save your Google Gemini API key.

On first startup, the backend downloads the Whisper small model (approximately 466 MB). This is a one-time download stored in a Docker volume.

The Docker Compose ports are bound to `127.0.0.1` so the development server is only exposed on the local machine.

## Create a video

1. Create a new idea and enter the topic.
2. Generate the script.
3. Upload one MP4 clip for each scene. Files are sorted by filename.
4. Generate the voiceover.
5. Synchronize the clips with the generated audio.
6. Generate subtitles and choose a background music track.
7. Download the completed video.

## Configuration

### Gemini API key

The API key can be saved from the **Gemini Key** dialog in the app. It is written to the local `config.json` file, which is excluded from Git.

Alternatively, set the environment variable before starting the backend:

```env
GEMINI_API_KEY=your_gemini_api_key
```

### Optional Discord / Midjourney integration

The repository also contains experimental Discord browser automation. It is not required by the current web workflow and is not configured through the web UI.

Its settings are read from the root `.env` file:

```env
DISCORD_EMAIL=your_discord_email
DISCORD_PASSWORD=your_discord_password
DISCORD_TOKEN=your_discord_authorization_token
DISCORD_CHAT_URL=https://discord.com/channels/...
DISCORD_MESSAGES_ENDPOINT=https://discord.com/api/v9/channels/.../messages
```

Do not commit `.env`, API keys, Discord credentials, or tokens. Discord UI automation is fragile and may break when Discord changes its interface or access policies.

## Architecture

| Directory | Purpose |
| --- | --- |
| `api/` | FastAPI application and HTTP endpoints |
| `frontend/` | React + TypeScript user interface |
| `flows/` | Video-creation pipeline, prompts, schemas, and generated assets |
| `tools/` | Gemini, Whisper, FFmpeg, Discord, and storage integrations |
| `.rules/` | Project architecture and coding standards |

## Development

### Frontend

```bash
cd frontend
npm ci
npm run typecheck
npm run build
```

### Backend

Python 3.11 or newer is required.

```bash
poetry install
poetry run python -m compileall api flows tools
```

### Docker

```bash
docker compose build
docker compose up
docker compose down
```

## Security

This application is designed for local development. The API currently has no user authentication, so do not expose the backend or frontend directly to the public internet. If deploying to a shared or public environment, add authentication, request-size limits, secret management, and a production reverse proxy first.

The local `config.json` file contains the Gemini API key in plaintext. Keep the machine and its local files secure.
