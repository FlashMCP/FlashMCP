"""FlashMCP - A more ergonomic interface for MCP servers."""

from importlib.metadata import version
from .server import FlashMCP, Context
from .utilities.types import Image

__version__ = version("FlashMCP")
__all__ = ["FlashMCP", "Context", "Image"]
