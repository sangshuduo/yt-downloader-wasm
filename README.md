# YouTube Video Downloader (WASM + Python)

A web-based YouTube video downloader that runs in the browser and uploads directly to AWS S3. Built with Rust WASM for URL validation and Python Flask for video processing.

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
│  │                    │   yt-dlp    │  │  yt-dlp + S3 Upload     │ │  │
│  │                    │  (Extract)  │  │  (Download & Upload)     │ │  │
│  │                    └──────────────┘  └────────────────────────────┘ │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
    ┌─────────────────┐  ┌─────────────┐  ┌──────────────────┐
    │   YouTube       │  │   Invidious │  │    AWS S3       │
    │   (Source)      │  │   (Backup)  │  │  huski-tmp-new  │
    └─────────────────┘  └─────────────┘  └──────────────────┘
```

## System Components

| Component | Technology | Description |
|-----------|------------|-------------|
| Frontend UI | HTML/CSS/JS | Browser-based user interface |
| URL Validation | Rust WASM | Fast URL parsing and video ID extraction |
| Video Processing | yt-dlp | YouTube video metadata extraction |
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
- **yt-dlp** (Python) for video extraction with signature decryption
- **Server-side streaming** for memory-efficient S3 upload

This hybrid approach provides reliability while keeping the browser responsive.

## Prerequisites

- Python 3.10+
- Node.js (for WASM compilation)
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
pip install flask yt-dlp boto3 gunicorn
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

**Response:**
```json
{
  "title": "Video Title",
  "formats": [
    {
      "quality": "1920x1080",
      "url": "https://...",
      "itag": "137",
      "ext": "mp4"
    }
  ],
  "duration": 213,
  "thumbnail": "https://..."
}
```

### POST /api/upload-s3

Downloads video and uploads to S3.

**Request Body:**
```json
{
  "url": "https://youtube.com/watch?v=...",
  "title": "Video Title",
  "quality": "1920x1080"
}
```

**Response:**
```json
{
  "success": true,
  "s3_url": "https://huski-tmp-new.s3.us-east-1.amazonaws.com/youtube/...",
  "filename": "video_20260219_120000_abc123.mp4"
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

### Server Port

Default port is 8080. Change in:

```bash
# Development
python server.py  # Uses port 8080

# Production  
gunicorn -b 0.0.0.0:9000 -c gunicorn_config.py server:app
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
- Increase timeout in `gunicorn_config.py` or use development mode

### "Could not find downloadable formats"
- Video may be age-restricted or unavailable
- Try using a VPN

### S3 Upload Fails
- Verify AWS credentials are correct
- Check S3 bucket permissions

### WASM Not Loading
- Ensure you're serving over HTTP (not file://)
- Check browser console for errors

## License

MIT License
