import contextlib

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing_extensions import Unpack

from FlashMCP.client.base import BaseClient, ClientKwargs


class StdioClient(BaseClient):
    def __init__(
        self,
        server_script_path: str,
        **kwargs: Unpack[ClientKwargs],
    ):
        super().__init__(**kwargs)
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
                **self._session_kwargs(),
            ) as session:
                async with self._set_session(transport, session):
                    yield self
