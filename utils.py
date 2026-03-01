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
    "pinterest": re.compile(
        r"(https?://)?(www\.|[a-z]{2}\.)?pinterest\.(com|ru|fr|de|co\.uk|it|es|pt|jp|se|dk|no|nz|au|ca|at|ch|be|mx|br|ar|cl|co|in|id|ph|sg|th|vn|za|ie|nl|pl|hu|ro|gr|cz|sk|bg|hr|si|lt|lv|ee)/pin/"
        r"|(https?://)?pin\.it/"
    ),
}


_YOUTUBE_SHORTS_RE = re.compile(r"(https?://)?(www\.)?youtube\.com/shorts/")


def is_youtube_url(url: str) -> bool:
    return bool(SUPPORTED_DOMAINS["youtube"].search(url))


def is_youtube_shorts_url(url: str) -> bool:
    return bool(_YOUTUBE_SHORTS_RE.search(url))


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
