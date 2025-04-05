import contextlib
import datetime

import mcp.types
from mcp import ClientSession
from mcp.client.sse import sse_client

from FlashMCP.client.base import (
    BaseClient,
    ListRootsFnT,
    LoggingFnT,
    MessageHandlerFnT,
    SamplingFnT,
)


class SSEClient(BaseClient):
    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        roots: list[mcp.types.Root] | None = None,
        sampling_callback: SamplingFnT | None = None,
        list_roots_callback: ListRootsFnT | None = None,
        logging_callback: LoggingFnT | None = None,
        message_handler: MessageHandlerFnT | None = None,
        read_timeout_seconds: datetime.timedelta | None = None,
    ):
        super().__init__(
            roots=roots,
            sampling_callback=sampling_callback,
            list_roots_callback=list_roots_callback,
            logging_callback=logging_callback,
            message_handler=message_handler,
            read_timeout_seconds=read_timeout_seconds,
        )
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
                sampling_callback=self._sampling_callback,
                list_roots_callback=self._list_roots_callback,
                logging_callback=self._logging_callback,
                message_handler=self._message_handler,
                read_timeout_seconds=self._read_timeout_seconds,
            ) as session:
                async with self._set_session(transport, session):
                    yield self
