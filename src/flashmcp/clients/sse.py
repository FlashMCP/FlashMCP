import contextlib

from mcp import ClientSession
from mcp.client.sse import sse_client
from typing_extensions import Unpack

from FlashMCP.clients.base import BaseClient, ClientKwargs


class SSEClient(BaseClient):
    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        **kwargs: Unpack[ClientKwargs],
    ):
        super().__init__(**kwargs)
        self.url = url
        self.headers = headers or {}

    @contextlib.asynccontextmanager
    async def _connect(self):
        """Set up SSE connection and session"""
        async with sse_client(self.url, headers=self.headers) as transport:
            read_stream, write_stream = transport
            async with ClientSession(
                read_stream=read_stream,
                write_stream=write_stream,
                **self._session_kwargs(),
            ) as session:
                async with self._set_session(transport, session):
                    yield self
