"""Configuração de logs: console + arquivo rotativo na pasta de dados."""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
from typing import Optional

LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(process)d] %(name)s: %(message)s"
LOG_FILENAME = "bim-schedule.log"
_configured_file: Optional[Path] = None


def configure_logging(level: str = "INFO", logs_dir: Optional[Path] = None) -> None:
    """Configura o logger ``bim_schedule``. Pode ser chamado novamente sem duplicar handlers."""
    global _configured_file
    logger = logging.getLogger("bim_schedule")
    logger.setLevel(level.upper())
    logger.propagate = False
    formatter = logging.Formatter(LOG_FORMAT)

    if not any(getattr(h, "_bim_console", False) for h in logger.handlers):
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console._bim_console = True  # type: ignore[attr-defined]
        logger.addHandler(console)

    if logs_dir is not None:
        log_file = (logs_dir / LOG_FILENAME).resolve()
        if _configured_file != log_file:
            for handler in [h for h in logger.handlers if getattr(h, "_bim_file", False)]:
                logger.removeHandler(handler)
                handler.close()
            logs_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8", delay=True
            )
            file_handler.setFormatter(formatter)
            file_handler._bim_file = True  # type: ignore[attr-defined]
            logger.addHandler(file_handler)
            _configured_file = log_file


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"bim_schedule.{name}")
