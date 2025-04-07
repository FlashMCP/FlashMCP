import contextlib

from mcp import ClientSession
from mcp.client.websocket import websocket_client
from typing_extensions import Unpack

from FlashMCP.clients.base import BaseClient, ClientKwargs


class WebSocketClient(BaseClient):
    def __init__(
        self,
        url: str,
        **kwargs: Unpack[ClientKwargs],
    ):
        super().__init__(**kwargs)
        self.url = url

    @contextlib.asynccontextmanager
    async def _connect(self):
        """Set up WebSocket connection and session"""
        async with websocket_client(self.url) as transport:
            read_stream, write_stream = transport

            async with ClientSession(
                read_stream=read_stream,
                write_stream=write_stream,
                **self._session_kwargs(),
            ) as session:
                async with self._set_session(transport, session):
                    yield self
