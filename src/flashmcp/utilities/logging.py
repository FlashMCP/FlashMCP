"""Logging utilities for FlashMCP."""

import logging
from typing import Literal

from rich.logging import RichHandler


def get_logger(name: str) -> logging.Logger:
    """Get a logger nested under FlashMCP namespace.

    Args:
        name: the name of the logger, which will be prefixed with 'FlashMCP.'

    Returns:
        a configured logger instance
    """
    return logging.getLogger(f"FlashMCP.{name}")


def configure_logging(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
) -> None:
    """Configure logging for FlashMCP.

    Args:
        level: the log level to use
    """
    logging.basicConfig(
        level=level, format="%(message)s", handlers=[RichHandler(rich_tracebacks=True)]
    )
