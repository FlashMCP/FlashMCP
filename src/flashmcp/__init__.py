"""FlashMCP - An ergonomic MCP interface."""

from importlib.metadata import version

from FlashMCP.server.server import FlashMCP
from FlashMCP.server.context import Context
import FlashMCP.server

from FlashMCP.client import Client
from FlashMCP.utilities.types import Image
from . import client, settings

__version__ = version("FlashMCP")
__all__ = [
    "FlashMCP",
    "Context",
    "client",
    "Client",
    "settings",
    "Image",
]
