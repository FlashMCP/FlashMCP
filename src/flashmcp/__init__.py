"""FlashMCP - An ergonomic MCP interface."""

from importlib.metadata import version
from FlashMCP.server import FlashMCP, Context

__version__ = version("FlashMCP")
__all__ = [
    "FlashMCP",
    "Context",
]
