from typing import Any

import mcp.server.FlashMCP
from FlashMCP.utilities.logging import get_logger

logger = get_logger(__name__)


class FlashMCP(mcp.server.FlashMCP.FlashMCP):
    def __init__(self, name: str | None = None, **settings: Any):
        super().__init__(name=name or "FlashMCP", **settings)
