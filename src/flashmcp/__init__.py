"""FlashMCP - A more ergonomic interface for MCP servers."""

from importlib.metadata import version
from mcp.server.FlashMCP import FlashMCP, Context, Image

__version__ = version("FlashMCP")
__all__ = ["FlashMCP", "Context", "Image"]
