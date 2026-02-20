# YouTube Video Downloader (WASM + Python + Invidious)

A web-based YouTube video downloader that runs in the browser and uploads directly to AWS S3. Built with Rust WASM for URL validation, Invidious for video extraction (with yt-dlp as backup), and Python Flask.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Client (Browser)                              │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                        Web UI (index.html)                           │  │
│  │  ┌──────────┐    ┌─────────────┐    ┌──────────────────────────┐  │  │
│  │  │  Input   │───▶│   WASM     │───▶│   Quality Selector     │  │  │
│  │  │  Form    │    │  (Rust)    │    │   (Radio Buttons)      │  │  │
│  │  └──────────┘    └─────────────┘    └───────────┬──────────────┘  │  │
│  │                                                │                   │  │
│  │                              ┌──────────────────┘                   │  │
│  │                              ▼                                      │  │
│  │                    ┌─────────────────────┐                        │  │
│  │                    │  Upload to S3 Button │                        │  │
│  │                    └──────────┬────────────┘                        │  │
│  └───────────────────────────────┼─────────────────────────────────────┘  │
└────────────────────────────────┼─────────────────────────────────────────┘
                                 │ HTTP
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Server (Flask + gunicorn)                        │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                         Flask Application                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │  │
│  │  │  /           │  │  /api/video   │  │  /api/upload-s3     │  │  │
│  │  │  (Static)   │  │  (GET)        │  │  (POST)             │  │  │
│  │  └──────────────┘  └───────┬────────┘  └──────────┬───────────┘  │  │
│  │                             │                       │               │  │
│  │                             ▼                       ▼               │  │
│  │                    ┌──────────────┐  ┌────────────────────────────┐ │  │
│  │                    │ Invidious or │  │  Video Download + S3 Upload │ │  │
│  │                    │   yt-dlp     │  │  (Download & Upload)       │ │  │
│  │                    │  (Extract)   │  │                            │ │  │
│  │                    └──────────────┘  └────────────────────────────┘ │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
    ┌─────────────────┐  ┌─────────────┐  ┌──────────────────┐
    │   YouTube       │  │  Invidious  │  │    AWS S3        │
    │   (Source)      │  │  (Local)    │  │  huski-tmp-new   │
    └─────────────────┘  └─────────────┘  └──────────────────┘
```

## System Components

| Component | Technology | Description |
|-----------|------------|-------------|
| Frontend UI | HTML/CSS/JS | Browser-based user interface |
| URL Validation | Rust WASM | Fast URL parsing and video ID extraction |
| Video Processing | Invidious / yt-dlp | YouTube video metadata extraction (configurable) |
| Backend Server | Python Flask | REST API for video operations |
| Cloud Storage | AWS S3 | Video file storage |
| WSGI Server | gunicorn | Production-grade server (Linux only) |

## Features

- 🌐 **Browser-based** - Works entirely in the browser
- 🔒 **Secure** - Videos uploaded directly to your S3 bucket
- 🎬 **Quality Selection** - Choose from available resolutions
- 📦 **MP4 Format** - Automatically selects MP4 format
- 🚀 **Concurrent Downloads** - Support for multiple simultaneous downloads
- ⚡ **WASM Powered** - Fast URL validation using WebAssembly
- 🔄 **Dual Backend** - Use yt-dlp (default) or Invidious with local proxy

## Why Server-Side Processing?

### WASM Limitation

While the project uses WebAssembly (WASM) for URL validation in the browser, **pure browser-based YouTube downloading is not practical** due to:

1. **Encrypted Video Streams** - YouTube uses signed URLs with `signatureCipher` that expire quickly. These require real-time signature decryption which is not possible in pure WASM.

2. **CORS Restrictions** - Browsers enforce Cross-Origin Resource Sharing (CORS) policies. YouTube's video CDN doesn't allow direct browser requests.

3. **Video+Audio Merging** - Most HD videos (720p+) have separate video and audio streams that need to be merged. This requires FFmpeg or similar tools that can't run in the browser.

4. **DRM and Encryption** - Many videos are encrypted or have DRM protection that prevents direct access.

### Solution

The current architecture uses:
- **WASM** for fast URL parsing and validation (client-side)
- **Invidious** (with companion) for video extraction via local proxy, hiding your IP from YouTube
- **yt-dlp** (Python) as default/fallback for video extraction with signature decryption
- **Server-side streaming** for memory-efficient S3 upload

This hybrid approach provides reliability while keeping the browser responsive.

## Prerequisites

- Python 3.10+
- Node.js (for WASM compilation)
- Docker & Docker Compose (for self-hosted Invidious)
- AWS credentials with S3 upload permissions
- Virtual environment (recommended)

## Installation

### 1. Clone and Setup

```bash
cd yt_downloader_wasm
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Compile WASM (Optional - pre-built included)

```bash
# Install wasm-pack if needed
cargo install wasm-pack

# Build WASM module
wasm-pack build --target web
```

### 4. Configure AWS Credentials

The server uses credentials from `~/.aws/credentials`. Ensure you have:

```
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
```

Or set environment variables:

```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

## Usage

### Development Mode

```bash
source venv/bin/activate
python server.py
```

Open http://localhost:8080 in your browser.

### Production Mode (Linux)

```bash
source venv/bin/activate
gunicorn -c gunicorn_config.py server:app
```

### Running on macOS

For macOS, use Flask's built-in threaded mode:

```bash
source venv/bin/activate
python server.py
```

Note: macOS has limitations with multiprocessing. For production deployments, use Linux.

## API Endpoints

### GET /

Serves the web UI.

### GET /api/video?url=<youtube_url>

Gets available video formats.

**Parameters:**
- `url` (required) - YouTube video URL
- `backend` (optional) - `yt-dlp` (default) or `invidious`

**Response:**
```json
{
  "title": "Video Title",
  "formats": [
    {
      "quality": "1080p",
      "url": "http://localhost:3000/videoplayback?...",
      "itag": "137",
      "ext": "mp4",
      "height": 1080
    }
  ],
  "duration": 213,
  "thumbnail": "https://...",
  "backend": "invidious"
}
```

### POST /api/upload-s3

Downloads video and uploads to S3.

**Request Body:**
```json
{
  "url": "https://youtube.com/watch?v=...",
  "title": "Video Title",
  "quality": "1080p",
  "backend": "invidious"
}
```

**Response:**
```json
{
  "success": true,
  "s3_url": "https://huski-tmp-new.s3.us-east-1.amazonaws.com/youtube/...",
  "filename": "video_20260219_120000_abc123.mp4",
  "backend": "invidious"
}
```

### GET /pkg/<path>

Serves compiled WASM files.

## Configuration

### S3 Bucket

Edit `server.py` to change the S3 bucket:

```python
S3_BUCKET = "your-bucket-name"
S3_REGION = "us-east-1"
```

### Backend Selection

The server supports two backends:
- **yt-dlp** (default) - Uses yt-dlp directly, most reliable
- **Invidious** - Uses local Invidious instance with companion for video proxy, hides your server IP from YouTube

**Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_BACKEND` | `yt-dlp` | Default backend: `yt-dlp` or `invidious` |
| `INVIDIOUS_URL` | `http://localhost:3000` | Invidious instance URL |

**Examples:**

```bash
# Use yt-dlp (default)
python server.py

# Use Invidious as default (requires local Invidious running)
DEFAULT_BACKEND=invidious python server.py

# Use custom Invidious instance
INVIDIOUS_URL=http://your-vps-ip:3000 DEFAULT_BACKEND=invidious python server.py
```

**Per-Request Override:**

You can override the backend for each request:

```bash
# Get video info using yt-dlp
curl "http://localhost:8080/api/video?url=...&backend=yt-dlp"
```

### Server Port

Default port is 8080. Change in:

```bash
# Development
python server.py  # Uses port 8080

# Production  
gunicorn -b 0.0.0.0:9000 -c gunicorn_config.py server:app
```

## Self-Hosted Invidious

The project includes a `docker-compose.yml` that runs Invidious with its companion service and PostgreSQL database. A local Invidious instance is **required** when using the `invidious` backend.

### Architecture

The Invidious stack consists of three services:
- **Invidious** - Main API server (port 3000)
- **Invidious Companion** - Handles video stream proxying and PO token generation
- **PostgreSQL** - Database for Invidious metadata

### Quick Start

1. Generate two random keys (max 16 characters each):

```bash
# Generate hmac_key
pwgen 16 1

# Generate invidious_companion_key (must match SERVER_SECRET_KEY in companion)
pwgen 16 1
```

2. Edit `docker-compose.yml` and replace the keys in:
   - `hmac_key` in the `INVIDIOUS_CONFIG` block
   - `invidious_companion_key` in the `INVIDIOUS_CONFIG` block
   - `SERVER_SECRET_KEY` in the companion service (must match `invidious_companion_key`)

3. Start Invidious:

```bash
docker compose up -d
```

4. Wait for database initialization (first run creates tables), then verify:

```bash
curl http://localhost:3000/api/v1/stats
```

### Using with Downloader

After Invidious is running:

```bash
# Local Invidious
DEFAULT_BACKEND=invidious python server.py

# Remote Invidious (VPS)
INVIDIOUS_URL=http://your-vps-ip:3000 DEFAULT_BACKEND=invidious python server.py
```

### Stop/Start

```bash
docker compose down       # Stop
docker compose up -d      # Start
docker compose logs -f    # View logs
```

### Concurrent Downloads

Edit `gunicorn_config.py`:

```python
workers = 3          # Number of worker processes
threads = 2          # Threads per worker
timeout = 600        # Request timeout (seconds)
```

## Project Structure

```
yt_downloader_wasm/
├── index.html           # Web UI
├── server.py            # Flask server
├── docker-compose.yml   # Invidious + Companion + PostgreSQL
├── requirements.txt     # Python dependencies
├── gunicorn_config.py   # Gunicorn configuration
├── Cargo.toml           # Rust project config
├── src/
│   └── lib.rs          # Rust WASM library
├── pkg/                 # Compiled WASM module
│   ├── yt_downloader_wasm.js
│   └── yt_downloader_wasm_bg.wasm
└── venv/               # Python virtual environment
```

## Troubleshooting

### "Connection reset by peer"
- If using Invidious, ensure the API is called with `local=true` so video streams are proxied through Invidious instead of downloading directly from Google CDN (already handled in current code)
- Increase timeout in `gunicorn_config.py` or use development mode for large files

### Invidious API errors
- Ensure all three Docker containers are running: `docker compose ps`
- Check Invidious logs: `docker compose logs invidious`
- Verify companion connectivity: `docker compose logs invidious-companion`
- Ensure `invidious_companion_key` matches `SERVER_SECRET_KEY`
- Fallback to yt-dlp: `DEFAULT_BACKEND=yt-dlp python server.py`

### "Could not find downloadable formats"
- Video may be age-restricted or unavailable
- Try using a VPN
- Switch backend: `?backend=yt-dlp`

### S3 Upload Fails
- Verify AWS credentials are correct
- Check S3 bucket permissions

### WASM Not Loading
- Ensure you're serving over HTTP (not file://)
- Check browser console for errors

## License

MIT License
