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
) -> None:
    """Configure logging for FlashMCP.

    Args:
        level: the log level to use
    """
    # Only configure the FlashMCP logger namespace
    handler = RichHandler(console=Console(stderr=True), rich_tracebacks=True)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    FlashMCP_logger = logging.getLogger("FlashMCP")
    FlashMCP_logger.setLevel(level)

    # Remove any existing handlers to avoid duplicates on reconfiguration
    for hdlr in FlashMCP_logger.handlers[:]:
        FlashMCP_logger.removeHandler(hdlr)

    FlashMCP_logger.addHandler(handler)
