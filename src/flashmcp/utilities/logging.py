"""Logging utilities for FlashMCP."""
import logging
from typing import Optional


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance nested under the FlashMCP namespace.
    
    Args:
        name: Optional name to append to the FlashMCP namespace.
            If provided, the logger will be named 'FlashMCP.[name]'.
            If not provided, returns the root FlashMCP logger.
    
    Returns:
        A configured logger instance
    """
    logger_name = "FlashMCP"
    if name:
        logger_name = f"{logger_name}.{name}"
    return logging.getLogger(logger_name)


def configure_logging(level: str = "INFO") -> None:
    """Configure the root FlashMCP logger.
    
    Args:
        level: The log level to use. Defaults to INFO.
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    get_logger().setLevel(getattr(logging, level.upper()))
