from typing import Any

import mcp.server.FlashMCP
from mcp.server.FlashMCP.utilities.logging import get_logger
from mcp.server.session import ServerSessionT
from mcp.shared.context import LifespanContextT, RequestContext
from mcp.types import (
    CreateMessageResult,
    ImageContent,
    SamplingMessage,
    TextContent,
)

logger = get_logger(__name__)


class Context(mcp.server.FlashMCP.Context[ServerSessionT, LifespanContextT]):
    def __init__(
        self,
        *,
        request_context: RequestContext[ServerSessionT, LifespanContextT] | None = None,
        FlashMCP: mcp.server.FlashMCP.FlashMCP | None = None,
        **kwargs: Any,
    ):
        super().__init__(request_context=request_context, FlashMCP=FlashMCP, **kwargs)

    async def sample(
        self,
        message: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> TextContent | ImageContent:
        """
        Send a sampling request to the client and await the response.

        Call this method at any time to have the server request an LLM
        completion from the client. The client must be appropriately configured,
        or the request will error.
        """

        if max_tokens is None:
            max_tokens = 512

        assert self._request_context is not None
        assert self._request_context.session is not None

        sampling_message = SamplingMessage(
            content=TextContent(text=message, type="text"),
            role="user",
        )

        result: CreateMessageResult = await self.request_context.session.create_message(
            messages=[sampling_message],
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return result.content
