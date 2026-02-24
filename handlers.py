import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction
from telegram.error import TelegramError

from downloader import download_video, cleanup_file
from utils import extract_url, is_supported_url, human_readable_size

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я умею скачивать видео с YouTube, TikTok и Instagram.\n\n"
        "Просто пришли мне ссылку — и я отправлю видео прямо в этот чат.\n\n"
        "Поддерживаемые платформы:\n"
        "  YouTube (видео и Shorts)\n"
        "  TikTok\n"
        "  Instagram (Reels, посты, IGTV)\n\n"
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
            "Пожалуйста, пришли корректную ссылку с YouTube, TikTok или Instagram."
        )
        return

    if not is_supported_url(url):
        await message.reply_text(
            "Эта ссылка не относится к поддерживаемым платформам.\n"
            "Поддерживаются: YouTube, TikTok, Instagram."
        )
        return

    status_msg = await message.reply_text("Скачиваю видео, подожди немного...")
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_VIDEO)

    result = await download_video(url)

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
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_VIDEO)

    try:
        with result.file_path.open("rb") as video_file:
            await message.reply_video(
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


def _classify_error(error_message: str) -> str:
    msg = error_message.lower()

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
