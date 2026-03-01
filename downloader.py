import asyncio
import os
import uuid
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import yt_dlp

from config import DOWNLOADS_DIR, TELEGRAM_FILE_LIMIT_BYTES, POT_PROVIDER_URL

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    success: bool
    file_path: Optional[Path] = None
    file_size_bytes: int = 0
    title: str = ""
    duration_seconds: int = 0
    error_message: str = ""
    too_large: bool = False
    webpage_url: str = ""


QUALITY_OPTIONS = [1080, 720, 480, 360]


def _build_ydl_opts(output_dir: str, unique_id: str, max_height: int = 1080, simple_format: bool = False) -> dict:
    output_template = os.path.join(output_dir, f"{unique_id}_%(title).50s.%(ext)s")
    base = {
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "logger": logger,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        # Раскомментируйте, если нужны куки для Instagram/TikTok:
        # "cookiefile": "cookies.txt",
    }
    yt_extractor_args: dict = {
        "youtube": {
            # ios отдаёт нормальный mp4 без cookies/po_token; tv_embedded — запасной
            "player_client": ["ios", "tv_embedded"],
        }
    }
    if POT_PROVIDER_URL:
        yt_extractor_args["youtubepot-bgutilhttp"] = {"base_url": [POT_PROVIDER_URL]}
    base["extractor_args"] = yt_extractor_args
    if not simple_format:
        base["format"] = (
            f"bestvideo[ext=mp4][height<={max_height}][vcodec!=none][ext!=mhtml]+bestaudio[ext=m4a]"
            f"/bestvideo[height<={max_height}][vcodec!=none][ext!=mhtml]+bestaudio"
            f"/best[height<={max_height}][vcodec!=none][ext!=mhtml]"
            "/best[vcodec!=none][ext!=mhtml]"
        )
        base["merge_output_format"] = "mp4"
    return base


async def download_video(url: str, max_height: int = 1080, simple_format: bool = False) -> DownloadResult:
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    unique_id = uuid.uuid4().hex[:8]
    opts = _build_ydl_opts(DOWNLOADS_DIR, unique_id, max_height=max_height, simple_format=simple_format)

    def _run_download() -> DownloadResult:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info is None:
                    return DownloadResult(
                        success=False,
                        error_message="yt-dlp не вернул метаданные для этого URL.",
                        webpage_url=url,
                    )

                if "entries" in info:
                    info = info["entries"][0]

                prepared_path = Path(ydl.prepare_filename(info))
                if not prepared_path.exists():
                    mp4_path = prepared_path.with_suffix(".mp4")
                    if mp4_path.exists():
                        prepared_path = mp4_path
                    else:
                        return DownloadResult(
                            success=False,
                            error_message="Загрузка завершилась, но файл не найден.",
                            webpage_url=url,
                        )

                file_size = prepared_path.stat().st_size
                too_large = file_size > TELEGRAM_FILE_LIMIT_BYTES

                return DownloadResult(
                    success=True,
                    file_path=prepared_path,
                    file_size_bytes=file_size,
                    title=info.get("title", "video"),
                    duration_seconds=int(info.get("duration") or 0),
                    too_large=too_large,
                    webpage_url=url,
                )

        except yt_dlp.utils.DownloadError as exc:
            return DownloadResult(
                success=False,
                error_message=str(exc),
                webpage_url=url,
            )
        except Exception as exc:
            logger.exception("Unexpected error in _run_download for %s", url)
            return DownloadResult(
                success=False,
                error_message=f"Неожиданная ошибка: {exc}",
                webpage_url=url,
            )

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run_download)


async def cleanup_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
        logger.info("Удалён временный файл: %s", path)
    except OSError as exc:
        logger.warning("Не удалось удалить %s: %s", path, exc)
