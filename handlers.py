import logging
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from telegram.error import TelegramError

from downloader import download_video, cleanup_file, QUALITY_OPTIONS
from utils import extract_url, is_supported_url, is_youtube_url, is_youtube_shorts_url, human_readable_size

logger = logging.getLogger(__name__)

CALLBACK_PREFIX = "quality:"
_URL_STORE_KEY = "pending_urls"


def _store_url(context: ContextTypes.DEFAULT_TYPE, url: str) -> str:
    """Save URL in bot_data and return a short key."""
    store = context.bot_data.setdefault(_URL_STORE_KEY, {})
    key = uuid.uuid4().hex[:12]
    store[key] = url
    return key


def _pop_url(context: ContextTypes.DEFAULT_TYPE, key: str) -> str | None:
    store = context.bot_data.get(_URL_STORE_KEY, {})
    return store.pop(key, None)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я умею скачивать видео с YouTube, TikTok, Instagram и Pinterest.\n\n"
        "Просто пришли мне ссылку — и я отправлю видео прямо в этот чат.\n\n"
        "Поддерживаемые платформы:\n"
        "  YouTube Shorts\n"
        "  TikTok\n"
        "  Instagram (Reels, посты, IGTV)\n"
        "  Pinterest\n\n"
        "Максимальный размер файла: 50 МБ."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_command(update, context)


async def handle_url_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    text = message.text or ""

    url = extract_url(text)
    if not url:
        await message.reply_text(
            "Пожалуйста, пришли корректную ссылку с YouTube, TikTok, Instagram или Pinterest."
        )
        return

    if not is_supported_url(url):
        await message.reply_text(
            "Эта ссылка не относится к поддерживаемым платформам.\n"
            "Поддерживаются: YouTube, TikTok, Instagram, Pinterest."
        )
        return

    if is_youtube_url(url) and not is_youtube_shorts_url(url):
        await message.reply_text(
            "Скачивание обычных YouTube-видео временно недоступно.\n"
            "Работают: YouTube Shorts, TikTok, Instagram, Pinterest."
        )
        return
    else:
        await _download_and_send(message, context, url, max_height=1080, simple_format=False)


async def _download_and_send(
    reply_target,
    context: ContextTypes.DEFAULT_TYPE,
    url: str,
    max_height: int = 1080,
    simple_format: bool = False,
    status_msg=None,
) -> None:
    """Download a video and send it. reply_target is a Message object."""
    chat_id = reply_target.chat_id

    if status_msg is None:
        status_msg = await reply_target.reply_text("Скачиваю видео, подожди немного...")
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)

    result = await download_video(url, max_height=max_height, simple_format=simple_format)

    if not result.success:
        user_facing_error = _classify_error(result.error_message)
        await status_msg.edit_text(f"Не удалось скачать: {user_facing_error}")
        return

    if result.too_large:
        size_str = human_readable_size(result.file_size_bytes)
        await status_msg.edit_text(
            f"Видео «{result.title}» весит {size_str}, что превышает лимит Telegram в 50 МБ.\n\n"
            f"Скачай его напрямую по ссылке:\n{url}"
        )
        if result.file_path:
            await cleanup_file(result.file_path)
        return

    await status_msg.edit_text("Загружаю в Telegram...")
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)

    try:
        with result.file_path.open("rb") as video_file:
            await reply_target.reply_video(
                video=video_file,
                caption=result.title,
                duration=result.duration_seconds or None,
                supports_streaming=True,
                read_timeout=120,
                write_timeout=120,
                connect_timeout=30,
            )
        await status_msg.delete()
    except TelegramError as exc:
        logger.error("Ошибка при отправке видео: %s", exc)
        await status_msg.edit_text(
            f"Видео скачано, но не удалось отправить в Telegram.\nОшибка: {exc}"
        )
    finally:
        if result.file_path:
            await cleanup_file(result.file_path)


async def handle_quality_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if not data.startswith(CALLBACK_PREFIX):
        return

    payload = data[len(CALLBACK_PREFIX):]
    sep = payload.index(":")
    max_height = int(payload[:sep])
    url_key = payload[sep + 1:]

    url = _pop_url(context, url_key)
    if not url:
        await query.edit_message_text("Ссылка устарела, пришли видео ещё раз.")
        return

    status_msg = await query.edit_message_text(f"Скачиваю видео в {max_height}p, подожди немного...")
    await _download_and_send(
        query.message,
        context,
        url,
        max_height=max_height,
        simple_format=False,
        status_msg=status_msg,
    )


def _classify_error(error_message: str) -> str:
    msg = error_message.lower()

    if "sign in to confirm" in msg or "confirm you're not a bot" in msg:
        return "YouTube требует подтверждения. Необходимо настроить cookies для бота."
    if "private" in msg or "login required" in msg or "age" in msg:
        return "Видео приватное или требует авторизации."
    if "not available" in msg or "unavailable" in msg:
        return "Видео недоступно (удалено или заблокировано в вашем регионе)."
    if "unsupported url" in msg:
        return "Ссылка не распознана или не поддерживается."
    if "no video formats" in msg or "no formats" in msg:
        return "Не найдено доступных форматов для скачивания."
    if "network" in msg or "connection" in msg or "timed out" in msg:
        return "Ошибка сети. Попробуй ещё раз."
    if "copyright" in msg:
        return "Видео заблокировано из-за авторских прав."

    parts = [p.strip() for p in error_message.split(":") if p.strip()]
    return parts[-1][:200] if parts else "Неизвестная ошибка."


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Необработанное исключение для update %s", update, exc_info=context.error)
    if isinstance(update, Update) and update.message:
        try:
            await update.message.reply_text(
                "Произошла непредвиденная ошибка. Попробуй ещё раз."
            )
        except TelegramError:
            pass
