use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn greet(name: &str) -> String {
    format!("Hello, {}! YouTube Downloader Ready!", name)
}

#[wasm_bindgen]
pub fn validate_youtube_url(url: &str) -> bool {
    let url_lower = url.to_lowercase();
    url_lower.contains("youtube.com") || url_lower.contains("youtu.be")
}

#[wasm_bindgen]
pub fn extract_video_id(url: &str) -> Option<String> {
    let patterns = [
        ("youtube.com/watch?v=", 16),
        ("youtu.be/", 9),
        ("youtube.com/embed/", 16),
        ("youtube.com/shorts/", 16),
        ("youtube.com/v/", 13),
    ];

    for (pattern, offset) in patterns {
        if let Some(pos) = url.find(pattern) {
            let start = pos + offset;
            let remaining = &url[start..];
            let end = remaining
                .find(&['&', '?', '#'][..])
                .unwrap_or(remaining.len());
            if end > 0 && end <= 20 {
                let id = remaining[..end].to_string();
                if !id.is_empty() && id.len() >= 8 {
                    return Some(id);
                }
            }
        }
    }
    None
}

#[wasm_bindgen]
pub fn sanitize_filename(name: &str) -> String {
    name.chars()
        .map(|c| match c {
            '/' | '\\' | ':' | '*' | '?' | '"' | '<' | '>' | '|' => '_',
            _ => c,
        })
        .collect::<String>()
        .trim()
        .to_string()
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

#[wasm_bindgen]
pub fn format_duration(seconds: u64) -> String {
    let hours = seconds / 3600;
    let minutes = (seconds % 3600) / 60;
    let secs = seconds % 60;

    if hours > 0 {
        format!("{:02}:{:02}:{:02}", hours, minutes, secs)
    } else {
        format!("{:02}:{:02}", minutes, secs)
    }
}

#[wasm_bindgen]
pub fn parse_quality(quality_str: &str) -> Option<u32> {
    if let Some(pos) = quality_str.find('x') {
        if let Ok(height) = quality_str[pos + 1..].parse::<u32>() {
            return Some(height);
        }
    }
    if let Ok(height) = quality_str.parse::<u32>() {
        return Some(height);
    }
    None
}

#[wasm_bindgen]
pub fn get_quality_label(height: u32) -> String {
    match height {
        144 => "144p".to_string(),
        240 => "240p".to_string(),
        360 => "360p".to_string(),
        480 => "480p SD".to_string(),
        720 => "720p HD".to_string(),
        1080 => "1080p Full HD".to_string(),
        1440 => "1440p QHD".to_string(),
        2160 => "2160p 4K UHD".to_string(),
        4320 => "4320p 8K UHD".to_string(),
        _ => format!("{}p", height),
    }
}

#[wasm_bindgen]
pub fn is_supported_quality(quality: &str) -> bool {
    let supported = [
        "256x144",
        "426x240",
        "640x360",
        "854x480",
        "1280x720",
        "1920x1080",
        "2560x1440",
        "3840x2160",
    ];
    supported
        .iter()
        .any(|s| s.starts_with(quality.split('x').next().unwrap_or("")))
}

#[wasm_bindgen]
pub fn generate_download_id() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis();
    format!("dl_{}", timestamp)
}
