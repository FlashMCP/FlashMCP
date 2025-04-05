from typing import Any

import mcp.server.FlashMCP

from FlashMCP.server.context import Context
from FlashMCP.utilities.logging import get_logger

logger = get_logger(__name__)


class FlashMCP(mcp.server.FlashMCP.FlashMCP):
    def __init__(self, name: str | None = None, **settings: Any):
        super().__init__(name=name or "FlashMCP", **settings)

    def get_context(self) -> Context:
        """
        Returns a Context object. Note that the context will only be valid
        during a request; outside a request, most methods will error.
        """
        try:
            request_context = self._mcp_server.request_context
        except LookupError:
            request_context = None
        return Context(request_context=request_context, FlashMCP=self)
