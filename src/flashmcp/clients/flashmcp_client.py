import contextlib
from typing import TypeVar

from mcp.shared.memory import create_connected_server_and_client_session
from typing_extensions import Unpack

from FlashMCP.clients.base import BaseClient, ClientKwargs
from FlashMCP.server.server import FlashMCP

T = TypeVar("T")


class FlashMCPClient(BaseClient):
    """Client that connects directly to an in-memory FlashMCP server.

    This client creates and manages an in-memory connection to a server,
    without using any external processes or network connections.
    """

    def __init__(
        self,
        server: FlashMCP,
        **kwargs: Unpack[ClientKwargs],
    ):
        """Initialize an InMemoryClient that connects to an in-memory MCP server.

        Args:
            server: The FlashMCP instance to connect to
            **kwargs: Additional arguments for BaseClient
        """
        super().__init__(**kwargs)
        self.server = server
        self._cm_session = None

    @contextlib.asynccontextmanager
    async def _connect(self):
        """Set up in-memory connection and session"""
        self._cm_session = create_connected_server_and_client_session(
            server=self.server._mcp_server,
            read_timeout_seconds=self._read_timeout_seconds,
            sampling_callback=self._sampling_callback,
            list_roots_callback=self._list_roots_callback,
            logging_callback=self._logging_callback,
            message_handler=self._message_handler,
        )

        async with self._cm_session as session:
            # No need to call initialize as create_connected_server_and_client_session already does
            async with self._set_session((None, None), session):
                yield self
