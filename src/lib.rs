use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn greet(name: &str) -> String {
    format!("Hello, {}! Welcome to YouTube Downloader WASM!", name)
}

#[wasm_bindgen]
pub fn validate_youtube_url(url: &str) -> bool {
    url.contains("youtube.com") || url.contains("youtu.be")
}

#[wasm_bindgen]
pub fn extract_video_id(url: &str) -> Option<String> {
    let patterns = [
        r"youtube.com/watch?v=",
        r"youtu.be/",
        r"youtube.com/embed/",
        r"youtube.com/shorts/",
    ];

    for pattern in patterns {
        if url.contains(pattern) {
            if let Some(pos) = url.find(pattern) {
                let start = pos + pattern.len();
                let remaining = &url[start..];
                let end = remaining.find(&['&', '?'][..]).unwrap_or(remaining.len());
                if end > 0 {
                    return Some(remaining[..end].to_string());
                }
            }
        }
    }
    None
}

#[wasm_bindgen]
pub fn format_file_size(bytes: u64) -> String {
    const KB: u64 = 1024;
    const MB: u64 = KB * 1024;
    const GB: u64 = MB * 1024;

    if bytes >= GB {
        format!("{:.2} GB", bytes as f64 / GB as f64)
    } else if bytes >= MB {
        format!("{:.2} MB", bytes as f64 / MB as f64)
    } else if bytes >= KB {
        format!("{:.2} KB", bytes as f64 / KB as f64)
    } else {
        format!("{} bytes", bytes)
    }
}
