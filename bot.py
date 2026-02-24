import logging
import sys
from telegram.ext import Application, CommandHandler, MessageHandler, filters

import config
from handlers import (
    start_command,
    help_command,
    handle_url_message,
    global_error_handler,
)


def configure_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        stream=sys.stdout,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def build_application() -> Application:
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(120)
        .connect_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url_message))
    app.add_error_handler(global_error_handler)

    return app


def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Запуск бота...")
    app = build_application()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
