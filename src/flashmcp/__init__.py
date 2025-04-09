"""FlashMCP - An ergonomic MCP interface."""

from importlib.metadata import version
import FlashMCP.settings

from FlashMCP.server.server import FlashMCP
from FlashMCP.server.context import Context
from . import clients

__version__ = version("FlashMCP")
__all__ = ["FlashMCP", "Context", "clients"]
