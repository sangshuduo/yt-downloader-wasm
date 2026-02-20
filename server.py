#!/usr/bin/env python3
"""
Simple Flask server for YouTube video downloading using yt-dlp.
Run: source venv/bin/activate && python server.py
Then open http://localhost:8080 in your browser
"""

from flask import Flask, request, jsonify, send_from_directory, Response
import yt_dlp
import json
import sys
import urllib.request
import boto3
import os
import uuid
from datetime import datetime
import time
import requests
import re
import random


# Increase Flask request timeout
class TimeoutMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # Set a longer timeout for the request
        return self.app(environ, start_response)


app = Flask(__name__)

# Backend Configuration
INVIDIOUS_URL = os.getenv("INVIDIOUS_URL", "http://localhost:3000")
# Auto-detect default backend from env: explicit > PIPED_API_URL > yt-dlp
if os.getenv("DEFAULT_BACKEND"):
    DEFAULT_BACKEND = os.getenv("DEFAULT_BACKEND")
elif os.getenv("PIPED_API_URL"):
    DEFAULT_BACKEND = "piped"
else:
    DEFAULT_BACKEND = "yt-dlp"

# Piped public API instances (randomly selected, with retry fallback)
# Full list from https://github.com/TeamPiped/documentation and community sources
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi-libre.kavin.rocks",
    "https://pipedapi.leptons.xyz",
    "https://pipedapi.r4fo.com",
    "https://api-piped.mha.fi",
    "https://piped-api.garudalinux.org",
    "https://pipedapi.rivo.lol",
    "https://piped-api.lunar.icu",
    "https://ytapi.dc09.ru",
    "https://pipedapi.colinslegacy.com",
    "https://yapi.vyper.me",
    "https://api.looleh.xyz",
    "https://piped-api.cfe.re",
    "https://pa.mint.lgbt",
    "https://pa.il.ax",
    "https://api.piped.projectsegfau.lt",
    "https://watchapi.whatever.social",
    "https://api.piped.privacydev.net",
    "https://pipedapi.palveluntarjoaja.eu",
    "https://pipedapi.smnz.de",
    "https://pipedapi.qdi.fi",
    "https://piped-api.hostux.net",
    "https://pdapi.vern.cc",
    "https://pipedapi.pfcd.me",
    "https://pipedapi.frontendfriendly.xyz",
    "https://api.piped.yt",
    "https://pipedapi.astartes.nl",
    "https://pipedapi.osphost.fi",
    "https://pipedapi.simpleprivacy.fr",
    "https://pipedapi.drgns.space",
    "https://piapi.ggtyler.dev",
    "https://api.watch.pluto.lat",
    "https://piped-backend.seitan-ayoub.lol",
    "https://api.piped.minionflo.net",
    "https://pipedapi.nezumi.party",
    "https://pipedapi.ducks.party",
    "https://pipedapi.ngn.tf",
    "https://piped-api.codespace.cz",
    "https://pipedapi.reallyaweso.me",
    "https://pipedapi.phoenixthrush.com",
    "https://api.piped.private.coffee",
    "https://schaunapi.ehwurscht.at",
    "https://pipedapi.darkness.services",
    "https://pipedapi.andreafortuna.org",
    "https://pipedapi.orangenet.cc",
    "https://pipedapi.owo.si",
    "https://pipedapi.nosebs.ru",
    "https://piped-api.privacy.com.de",
    "https://pipedapi.coldforge.xyz",
    "https://piped.wireway.ch",
]
# Allow overriding with a custom instance list via env var (comma-separated)
if os.getenv("PIPED_INSTANCES"):
    PIPED_INSTANCES = [u.strip() for u in os.getenv("PIPED_INSTANCES").split(",")]
# Self-hosted Piped instance URL (used when running Piped via Docker Compose)
PIPED_SELF_HOSTED_URL = os.getenv("PIPED_API_URL", "")

# S3 Configuration
S3_BUCKET = os.getenv("S3_BUCKET", "huski-tmp-new")
S3_REGION = os.getenv("AWS_REGION", "us-east-1")


def extract_video_id(url):
    """Extract YouTube video ID from URL."""
    import re

    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_video_info_invidious(video_id):
    """Get video info from Invidious API."""
    import requests

    api_url = f"{INVIDIOUS_URL}/api/v1/videos/{video_id}?local=true"
    print(f"Fetching video info from Invidious: {api_url}", file=sys.stderr)

    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        data = response.json()

        formats = []
        for fmt in data.get("adaptiveFormats", []):
            if fmt.get("type", "").startswith("video") and fmt.get("url"):
                itag = fmt.get("itag", "")
                # Extract height from resolution field (e.g. "1080p" -> 1080)
                resolution = fmt.get("resolution", "")
                quality_label = fmt.get("qualityLabel", "")
                height = fmt.get("height") or 0
                if not height and resolution:
                    match = re.match(r"(\d+)p", resolution)
                    if match:
                        height = int(match.group(1))
                if height > 0:
                    url = fmt.get("url", "")
                    # local=true returns relative URLs, prepend Invidious host
                    if url.startswith("/"):
                        url = f"{INVIDIOUS_URL}{url}"
                    formats.append(
                        {
                            "quality": quality_label or f"{height}p",
                            "url": url,
                            "itag": str(itag),
                            "ext": "mp4",
                            "height": height,
                        }
                    )

        # Deduplicate by height, keeping first (usually mp4/avc1)
        seen_heights = set()
        unique_formats = []
        for fmt in formats:
            if fmt["height"] not in seen_heights:
                seen_heights.add(fmt["height"])
                unique_formats.append(fmt)
        formats = unique_formats

        # Sort by height descending
        formats.sort(key=lambda x: x["height"], reverse=True)

        return {
            "title": data.get("title", "YouTube Video"),
            "thumbnail": data.get("thumbnailUrl"),
            "duration": data.get("lengthSeconds", 0),
            "formats": formats[:10],
            "videoId": video_id,
        }
    except Exception as e:
        print(f"Invidious API error: {e}", file=sys.stderr)
        raise Exception(f"Invidious error: {str(e)}")


def _parse_piped_streams(data):
    """Parse videoStreams from a Piped API response into our format list.

    Prefers combined (audio+video) streams, then supplements with video-only
    streams for higher quality options not available as combined.
    """
    combined = []
    video_only = []

    for fmt in data.get("videoStreams", []):
        if not fmt.get("url"):
            continue
        height = fmt.get("height", 0)
        quality = fmt.get("quality", "")
        # Some streams (e.g. combined 360p) have height=0; parse from quality string
        if not height and quality:
            match = re.match(r"(\d+)p", quality)
            if match:
                height = int(match.group(1))
        if height <= 0:
            continue
        entry = {
            "quality": quality or f"{height}p",
            "url": fmt["url"],
            "itag": str(fmt.get("itag", "")),
            "ext": "mp4",
            "height": height,
        }
        if fmt.get("videoOnly", True):
            video_only.append(entry)
        else:
            combined.append(entry)

    # Start with combined streams, then add video-only for heights not covered
    formats = list(combined)
    combined_heights = {f["height"] for f in combined}
    for fmt in video_only:
        if fmt["height"] not in combined_heights:
            formats.append(fmt)

    # Deduplicate by height
    seen_heights = set()
    unique_formats = []
    for fmt in formats:
        if fmt["height"] not in seen_heights:
            seen_heights.add(fmt["height"])
            unique_formats.append(fmt)
    formats = unique_formats

    formats.sort(key=lambda x: x["height"], reverse=True)
    return formats


def _try_piped_instance(instance_url, video_id):
    """Try a single Piped instance. Returns result dict or raises on failure."""
    api_url = f"{instance_url}/streams/{video_id}"
    print(f"Trying Piped instance: {api_url}", file=sys.stderr)

    response = requests.get(api_url, timeout=10, allow_redirects=False)

    # Reject redirects (often means the instance is misconfigured)
    if response.is_redirect or response.status_code in (301, 302, 307, 308):
        raise Exception(f"Redirected (HTTP {response.status_code})")

    # Try to parse JSON even on error status codes (Piped returns JSON errors)
    try:
        data = response.json()
    except Exception:
        response.raise_for_status()
        raise Exception(f"Non-JSON response (HTTP {response.status_code})")

    if data.get("error"):
        error_msg = str(data.get("message", data["error"]))[:150]
        raise Exception(f"API error: {error_msg}")

    if response.status_code >= 400:
        raise Exception(f"HTTP {response.status_code}")

    if not data.get("title"):
        raise Exception("Empty response (no title)")

    formats = _parse_piped_streams(data)

    print(
        f"Piped instance {instance_url} returned {len(formats)} formats",
        file=sys.stderr,
    )

    return {
        "title": data.get("title", "YouTube Video"),
        "thumbnail": data.get("thumbnailUrl"),
        "duration": data.get("duration", 0),
        "formats": formats[:10],
        "videoId": video_id,
        "piped_instance": instance_url,
    }


# Max public instances to try before giving up (avoids very long waits)
PIPED_MAX_ATTEMPTS = int(os.getenv("PIPED_MAX_ATTEMPTS", "8"))


def get_video_info_piped(video_id):
    """Get video info from Piped API with random instance selection and retry."""
    last_error = None

    # If a self-hosted instance is configured, use only that
    if PIPED_SELF_HOSTED_URL:
        return _try_piped_instance(PIPED_SELF_HOSTED_URL, video_id)

    # Otherwise, try random public instances
    instances = list(PIPED_INSTANCES)
    random.shuffle(instances)
    tried = 0

    for instance_url in instances:
        if tried >= PIPED_MAX_ATTEMPTS:
            print(
                f"Piped: reached max attempts ({PIPED_MAX_ATTEMPTS}), stopping",
                file=sys.stderr,
            )
            break
        tried += 1

        try:
            return _try_piped_instance(instance_url, video_id)
        except requests.exceptions.RequestException as e:
            print(f"Piped instance {instance_url} failed: {e}", file=sys.stderr)
            last_error = str(e)
            continue
        except Exception as e:
            print(f"Piped instance {instance_url} error: {e}", file=sys.stderr)
            last_error = str(e)
            continue

    raise Exception(
        f"All Piped instances failed (tried {tried}). Last error: {last_error}"
    )


# Initialize S3 client - reads from ~/.aws/credentials by default
s3_client = boto3.client(
    "s3",
    region_name=S3_REGION,
)

# Store active uploads for progress tracking
active_uploads = {}


@app.route("/")
def index():
    """Serve the main page with default backend injected."""
    with open("index.html", "r") as f:
        html = f.read()
    html = html.replace(
        "<!--SERVER_CONFIG-->",
        f"<script>window.DEFAULT_BACKEND = '{DEFAULT_BACKEND}';</script>",
    )
    return html


@app.route("/pkg/<path:filename>")
def serve_pkg(filename):
    """Serve WASM package files."""
    return send_from_directory("pkg", filename)


@app.route("/api/video")
def get_video():
    """API endpoint to get video info."""
    url = request.args.get("url")
    backend = request.args.get("backend", DEFAULT_BACKEND)

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    # Override backend if specified in query param
    if request.args.get("backend"):
        backend = request.args.get("backend")

    print(f"Using backend: {backend} for video info", file=sys.stderr)

    # Extract video ID for Invidious
    video_id = extract_video_id(url)

    if backend == "invidious" and video_id:
        try:
            info = get_video_info_invidious(video_id)
            info["backend"] = "invidious"
            return jsonify(info)
        except Exception as e:
            return jsonify({"error": str(e), "backend": "invidious"}), 500

    if backend == "piped" and video_id:
        try:
            info = get_video_info_piped(video_id)
            info["backend"] = "piped"
            return jsonify(info)
        except Exception as e:
            return jsonify({"error": str(e), "backend": "piped"}), 500

    # Default: use yt-dlp
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "best[ext=mp4]/best",
        "extract_flat": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = []

        # Get all video formats - only MP4
        if "formats" in info:
            for fmt in info["formats"]:
                # Only include video formats with direct URLs, prefer mp4
                if fmt.get("url") and fmt.get("vcodec", "none") != "none":
                    ext = fmt.get("ext", "")
                    if ext == "mp4":  # Only show mp4 formats
                        quality = fmt.get("resolution", fmt.get("height", "Unknown"))
                        # Add more detail to quality string
                        if fmt.get("height"):
                            quality = f"{fmt.get('width', '')}x{fmt.get('height')}"
                        formats.append(
                            {
                                "quality": str(quality),
                                "url": fmt.get("url"),
                                "itag": fmt.get("format_id"),
                                "ext": fmt.get("ext", "mp4"),
                            }
                        )

        # If no formats found, try the best format
        if not formats and info.get("url"):
            formats.append(
                {
                    "quality": "best",
                    "url": info.get("url"),
                    "itag": "best",
                    "ext": "mp4",
                }
            )

        result = {
            "title": info.get("title", "YouTube Video"),
            "formats": formats[:10],
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "backend": "yt-dlp",
        }

        return jsonify(result)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return jsonify({"error": str(e)}), 500


@app.route("/api/upload-s3", methods=["POST"])
def upload_to_s3():
    """Download video and upload to S3."""
    data = request.get_json()
    video_url = data.get("url")
    title = data.get("title", "video")
    quality = data.get("quality", "best")
    backend = data.get("backend", DEFAULT_BACKEND)

    if not video_url:
        return jsonify({"error": "No URL provided"}), 400

    print(
        f"Starting S3 upload for: {title} (quality: {quality}, backend: {backend})",
        file=sys.stderr,
    )

    # Generate unique filename
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:50]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    s3_key = f"youtube/{safe_title}_{timestamp}_{unique_id}.mp4"
    temp_dir = "/tmp"
    temp_filename = f"{temp_dir}/yt_{unique_id}.mp4"

    try:
        if backend in ("invidious", "piped"):
            video_id = extract_video_id(video_url)
            if not video_id:
                raise Exception("Could not extract video ID from URL")

            # Get video info from the selected backend
            if backend == "piped":
                info = get_video_info_piped(video_id)
            else:
                info = get_video_info_invidious(video_id)

            # Select format based on quality
            selected_format = None
            if quality and quality != "best":
                # Parse target height from quality string like "1080p" or "1920x1080"
                target_height = 0
                height_match = re.search(r"(\d+)p?$", str(quality))
                if height_match:
                    target_height = int(height_match.group(1))
                for fmt in info.get("formats", []):
                    fmt_height = fmt.get("height", 0)
                    if fmt_height and fmt_height <= target_height:
                        selected_format = fmt
                        break
            if not selected_format and info.get("formats"):
                selected_format = info["formats"][0]  # Best quality

            if not selected_format:
                raise Exception("No suitable format found")

            direct_url = selected_format["url"]
            print(f"Downloading from {backend}: {direct_url[:80]}...", file=sys.stderr)

            # Download video from direct URL
            req = urllib.request.Request(direct_url)
            req.add_header("User-Agent", "Mozilla/5.0")
            req.add_header("Accept", "*/*")

            with open(temp_filename, "wb") as f:
                response = urllib.request.urlopen(req, timeout=600)
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                response.close()

        else:
            # yt-dlp path (default)
            # Parse quality - could be "1280x720" or "best"
            if quality and quality != "best":
                try:
                    if "x" in str(quality):
                        height = int(quality.split("x")[1])
                        format_str = f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best"
                    else:
                        format_str = f"format_id/{quality}/best"
                except Exception as e:
                    print(f"Parse error: {e}", file=sys.stderr)
                    format_str = "bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best"
            else:
                format_str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

            print(f"Using format: {format_str}, quality: {quality}", file=sys.stderr)

            # Download video to temp file using yt-dlp
            print(
                f"Downloading video using yt-dlp to {temp_filename}...", file=sys.stderr
            )

            ydl_opts = {
                "format": format_str,
                "outtmpl": temp_filename,
                "quiet": True,
                "no_warnings": True,
                "retries": 3,
                "fragment_retries": 3,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

        # Upload temp file to S3
        print(f"Uploading {temp_filename} to S3...", file=sys.stderr)

        try:
            with open(temp_filename, "rb") as f:
                s3_client.put_object(
                    Bucket=S3_BUCKET,
                    Key=s3_key,
                    Body=f,
                    ContentType="video/mp4",
                    ACL="public-read",
                )
            os.remove(temp_filename)
        except Exception as e:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            print(f"S3 upload error: {e}", file=sys.stderr)
            raise Exception(f"Failed to upload to S3: {str(e)}")

        # Generate S3 URL
        s3_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_key}"

        print(f"Upload complete: {s3_url}", file=sys.stderr)

        return jsonify(
            {
                "success": True,
                "s3_url": s3_url,
                "filename": s3_key.split("/")[-1],
                "backend": backend,
            }
        )

    except Exception as e:
        print(f"S3 Upload error: {e}", file=sys.stderr)
        return jsonify({"error": str(e)}), 500


@app.route("/api/download")
def download_video():
    """Proxy to download video (bypasses CORS)."""
    video_url = request.args.get("url")
    title = request.args.get("title", "video")

    if not video_url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "best[ext=mp4]/best",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            direct_url = info["url"]

        req = urllib.request.Request(direct_url)
        req.add_header("User-Agent", "Mozilla/5.0")

        response = urllib.request.urlopen(req, timeout=30)

        content_type = response.headers.get("Content-Type", "video/mp4")
        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:50]
        filename = f"{safe_title}.mp4"

        def generate():
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                yield chunk
            response.close()

        return Response(
            generate(),
            content_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": response.headers.get("Content-Length", ""),
            },
        )

    except Exception as e:
        print(f"Download error: {e}", file=sys.stderr)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("Starting YouTube Downloader Server...")
    print(f"Default backend: {DEFAULT_BACKEND}")
    print(f"Invidious URL: {INVIDIOUS_URL}")
    print(f"Piped instances: {len(PIPED_INSTANCES)} configured")
    print(f"Uploading to S3 bucket: {S3_BUCKET}")
    print("Open http://localhost:8080 in your browser")
    print("Multiple concurrent downloads: ENABLED")
    print("Press Ctrl+C to stop")
    # Use threaded=True to handle multiple simultaneous downloads
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)

# Expose app for gunicorn
application = app
