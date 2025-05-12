"""Logging utilities for FlashMCP."""

import logging
from typing import Literal

from rich.console import Console
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
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | int = "INFO",
    logger: logging.Logger | None = None,
) -> None:
    """
    Configure logging for FlashMCP.

    Args:
        logger: the logger to configure
        level: the log level to use
    """
    if logger is None:
        logger = logging.getLogger("FlashMCP")

    # Only configure the FlashMCP logger namespace
    handler = RichHandler(console=Console(stderr=True), rich_tracebacks=True)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    logger.setLevel(level)

    # Remove any existing handlers to avoid duplicates on reconfiguration
    for hdlr in logger.handlers[:]:
        logger.removeHandler(hdlr)

    logger.addHandler(handler)
