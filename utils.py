import re
from urllib.parse import urlparse

SUPPORTED_DOMAINS = {
    "youtube": re.compile(
        r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)"
    ),
    "tiktok": re.compile(
        r"(https?://)?(www\.|vm\.)?tiktok\.com/"
    ),
    "instagram": re.compile(
        r"(https?://)?(www\.)?instagram\.com/(p|reel|tv)/"
    ),
}


def extract_url(text: str) -> str | None:
    tokens = text.split()
    for token in tokens:
        parsed = urlparse(token)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return token
    return None


def is_supported_url(url: str) -> bool:
    return any(pattern.search(url) for pattern in SUPPORTED_DOMAINS.values())


def human_readable_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"
