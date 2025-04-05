import contextlib
import datetime

import mcp.types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from FlashMCP.client.base import (
    BaseClient,
    ListRootsFnT,
    LoggingFnT,
    MessageHandlerFnT,
    SamplingFnT,
)


class StdioClient(BaseClient):
    def __init__(
        self,
        server_script_path: str,
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
        self.server_script_path = server_script_path

    @contextlib.asynccontextmanager
    async def _connect(self):
        """Set up stdio connection and session"""
        is_python = self.server_script_path.endswith(".py")
        is_js = self.server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command, args=[self.server_script_path], env=None
        )

        async with stdio_client(server_params) as transport:
            stdio, write = transport

            async with ClientSession(
                read_stream=stdio,
                write_stream=write,
                sampling_callback=self._sampling_callback,
                list_roots_callback=self._list_roots_callback,
                logging_callback=self._logging_callback,
                message_handler=self._message_handler,
                read_timeout_seconds=self._read_timeout_seconds,
            ) as session:
                async with self._set_session(transport, session):
                    yield self
