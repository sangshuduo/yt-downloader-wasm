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


# Increase Flask request timeout
class TimeoutMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # Set a longer timeout for the request
        return self.app(environ, start_response)


app = Flask(__name__)

# S3 Configuration
S3_BUCKET = os.getenv("S3_BUCKET", "huski-tmp-new")
S3_REGION = os.getenv("AWS_REGION", "us-east-1")

# Initialize S3 client - reads from ~/.aws/credentials by default
s3_client = boto3.client(
    "s3",
    region_name=S3_REGION,
)
    s3_client = None
else:
    s3_client = boto3.client(
        "s3",
        region_name=S3_REGION,
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
    )


@app.route("/")
def index():
    """Serve the main page."""
    with open("index.html", "r") as f:
        return f.read()


@app.route("/pkg/<path:filename>")
def serve_pkg(filename):
    """Serve WASM package files."""
    return send_from_directory("pkg", filename)


@app.route("/api/video")
def get_video():
    """API endpoint to get video info using yt-dlp."""
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

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

    if not video_url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        print(f"Starting S3 upload for: {title} (quality: {quality})", file=sys.stderr)

        # Parse quality - could be "1280x720" or "best"
        if quality and quality != "best":
            try:
                if "x" in str(quality):
                    # It's a resolution like "1280x720"
                    height = int(quality.split("x")[1])
                    # Use mp4 format only
                    format_str = f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]/best"
                else:
                    # It's a format_id/itag
                    format_str = f"format_id/{quality}/best"
            except Exception as e:
                print(f"Parse error: {e}", file=sys.stderr)
                format_str = "bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best"
        else:
            # Default: prefer mp4
            format_str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

        print(f"Using format: {format_str}, quality: {quality}", file=sys.stderr)

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": format_str,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

            # Debug: print selected format info
            print(
                f"Selected format: {info.get('format_id')}, height: {info.get('height')}, resolution: {info.get('resolution')}",
                file=sys.stderr,
            )

            # Get direct URL - try different sources
            direct_url = info.get("url")

            # Fallback: check requested_formats for video+audio merged format
            if not direct_url and info.get("requested_formats"):
                for fmt in info.get("requested_formats", []):
                    if fmt.get("url") and fmt.get("vcodec", "none") != "none":
                        direct_url = fmt.get("url")
                        print(
                            f"Got URL from requested_formats: {fmt.get('format_id')}",
                            file=sys.stderr,
                        )
                        break

            if not direct_url:
                raise Exception("Could not get video URL")

            print(f"Got video URL", file=sys.stderr)

            # Fallback: check requested_formats
            if not direct_url and info.get("requested_formats"):
                for fmt in info.get("requested_formats", []):
                    if fmt.get("url") and fmt.get("vcodec", "none") != "none":
                        direct_url = fmt.get("url")
                        break

            if not direct_url:
                raise Exception("Could not get video URL")

            print(f"Got video URL", file=sys.stderr)

        # Generate unique filename
        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        s3_key = f"youtube/{safe_title}_{timestamp}_{unique_id}.mp4"

        # Download video content
        print(f"Downloading video from: {direct_url[:80]}...", file=sys.stderr)

        req = urllib.request.Request(direct_url)
        req.add_header("User-Agent", "Mozilla/5.0")
        req.add_header("Range", "bytes=0-")  # Support partial content

        # Use longer timeout for download
        response = urllib.request.urlopen(req, timeout=300)
        video_data = response.read()
        response.close()

        print(
            f"Downloaded {len(video_data)} bytes, uploading to S3...", file=sys.stderr
        )

        # Upload to S3
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=video_data,
            ContentType="video/mp4",
            ACL="public-read",
        )

        # Generate S3 URL
        s3_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_key}"

        print(f"Upload complete: {s3_url}", file=sys.stderr)

        return jsonify(
            {"success": True, "s3_url": s3_url, "filename": s3_key.split("/")[-1]}
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
    print("Using yt-dlp for video extraction")
    print(f"Uploading to S3 bucket: {S3_BUCKET}")
    print("Open http://localhost:8080 in your browser")
    print("Multiple concurrent downloads: ENABLED")
    print("Press Ctrl+C to stop")
    # Use threaded=True to handle multiple simultaneous downloads
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)

# Expose app for gunicorn
application = app
