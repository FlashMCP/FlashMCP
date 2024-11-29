"""FlashMCP - A more ergonomic interface for MCP servers."""

import asyncio
import base64
import functools
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence, Union, Literal

from mcp.server import Server as MCPServer
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport
from mcp.types import Resource as MCPResource
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from .exceptions import ResourceError
from .resources import Resource, FunctionResource, ResourceManager
from .tools import ToolManager
from .utilities import get_logger, configure_logging

logger = get_logger(__name__)


class Settings(BaseSettings):
    """FlashMCP server settings.

    All settings can be configured via environment variables with the prefix FASTMCP_.
    For example, FASTMCP_DEBUG=true will set debug=True.
    """

    model_config: dict = dict(env_prefix="FASTMCP_")

    # Server settings
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # HTTP settings
    host: str = "0.0.0.0"
    port: int = 8000

    # resource settings
    warn_on_duplicate_resources: bool = True

    # tool settings
    warn_on_duplicate_tools: bool = True


class FlashMCP:
    def __init__(self, name=None, **settings: Optional[Settings]):
        self.settings = Settings(**settings)
        self._mcp_server = MCPServer(name=name or "FlashMCP")
        self._tool_manager = ToolManager(
            warn_on_duplicate_tools=self.settings.warn_on_duplicate_tools
        )
        self._resource_manager = ResourceManager(
            warn_on_duplicate_resources=self.settings.warn_on_duplicate_resources
        )

        # Configure logging
        configure_logging(self.settings.log_level)

        self._setup_handlers()

    @property
    def name(self) -> str:
        return self._mcp_server.name

    def _setup_handlers(self) -> None:
        """Set up core MCP protocol handlers."""

        @self._mcp_server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            tools = self._tool_manager.list_tools()
            return [
                Tool(
                    name=info.name,
                    description=info.description,
                    inputSchema=info.parameters,
                )
                for info in tools
            ]

        @self._mcp_server.call_tool()
        async def handle_call_tool(
            name: str, arguments: dict
        ) -> Sequence[Union[TextContent, ImageContent, EmbeddedResource]]:
            result = await self._tool_manager.call_tool(name, arguments)
            return [self._convert_to_content(result)]

        @self._mcp_server.list_resources()
        async def handle_list_resources() -> list[MCPResource]:
            resources = self._resource_manager.list_resources()
            return [
                MCPResource(
                    uri=resource.uri,
                    name=resource.name,
                    description=resource.description,
                    mimeType=resource.mime_type,
                )
                for resource in resources
            ]

        @self._mcp_server.read_resource()
        async def handle_read_resource(uri: str) -> Union[str, bytes]:
            resource = self._resource_manager.get_resource(uri)
            if not resource:
                raise ResourceError(f"Unknown resource: {uri}")

            try:
                return await resource.read()
            except Exception as e:
                logger.error(f"Error reading resource {uri}: {e}")
                raise ResourceError(str(e))

    def _convert_to_content(
        self, value: Any
    ) -> Union[TextContent, ImageContent, EmbeddedResource]:
        """Convert Python values to MCP content types."""
        if isinstance(value, (dict, list)):
            return TextContent(type="text", text=json.dumps(value, indent=2))
        if isinstance(value, str):
            return TextContent(type="text", text=value)
        if isinstance(value, bytes):
            return ImageContent(
                type="image",
                data=base64.b64encode(value).decode(),
                mimeType="application/octet-stream",
            )
        if isinstance(value, BaseModel):
            return TextContent(type="text", text=value.model_dump_json(indent=2))
        return TextContent(type="text", text=str(value))

    def add_tool(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Add a tool to the server."""
        self._tool_manager.add_tool(func, name=name, description=description)

    def tool(
        self, name: Optional[str] = None, description: Optional[str] = None
    ) -> Callable:
        """Decorator to register a tool."""

        def decorator(func: Callable) -> Callable:
            self.add_tool(func, name=name, description=description)
            return func

        return decorator

    def add_resource(self, resource: Resource) -> None:
        """Add a resource to the server.

        Args:
            resource: A Resource instance to add
        """
        self._resource_manager.add_resource(resource)

    def add_file_resource(
        self,
        path: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> None:
        """Add a file as a resource.

        This is a convenience method that constructs and adds a FileResource.
        For more control, use add_resource() directly.
        """
        from pathlib import Path
        from .resources import FileResource

        file = Path(path)
        if not file.is_absolute():
            raise ValueError(f"Path must be absolute: {path}")
        if not file.is_file():
            raise FileNotFoundError(f"File does not exist: {path}")

        resource = FileResource(
            uri=f"file://{str(file)}",
            name=name or file.name,
            description=description,
            mime_type=mime_type or "text/plain",
            path=file,
        )
        self.add_resource(resource)

    def add_http_resource(
        self,
        url: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Add an HTTP endpoint as a resource.

        This is a convenience method that constructs and adds an HttpResource.
        For more control, use add_resource() directly.
        """
        from .resources import HttpResource

        resource = HttpResource(
            uri=f"http://{url}",
            name=name or url.split("/")[-1],
            description=description,
            mime_type=mime_type or "text/plain",
            url=url,
            headers=headers,
        )
        self.add_resource(resource)

    def add_dir_resource(
        self,
        path: str,
        *,
        recursive: bool = False,
        pattern: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Add a directory as a resource.

        This is a convenience method that constructs and adds a DirectoryResource.
        For more control, use add_resource() directly.
        """
        from pathlib import Path
        from .resources import DirectoryResource

        dir_path = Path(path).expanduser().resolve()
        if not dir_path.is_dir():
            raise ValueError(f"Directory does not exist: {path}")

        resource = DirectoryResource(
            uri=f"dir://{str(dir_path)}",
            name=name or dir_path.name,
            description=description,
            path=dir_path,
            recursive=recursive,
            pattern=pattern,
        )
        self.add_resource(resource)

    def resource(
        self,
        name: str,
        *,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> Callable:
        """Decorator to register a function as a dynamic resource.

        The function will be called with kwargs parsed from the URI query string.
        For example, a URI of "fn://my_func?x=1&y=2" will call the function with
        kwargs {"x": "1", "y": "2"}.

        Args:
            name: Name for the resource (used in fn:// URI)
            description: Optional description of the resource
            mime_type: Optional MIME type for the resource

        Example:
            @server.resource("my_func")
            def get_data(x: str, y: str) -> str:
                # Called with fn://my_func?x=1&y=2
                return f"x={x}, y={y}"
        """

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(**kwargs) -> Any:
                return func(**kwargs)

            resource = FunctionResource(
                uri=f"fn://{name}",  # Base URI, params added when called
                name=name,
                description=description,
                mime_type=mime_type or "text/plain",
                func=wrapper,
            )
            self.add_resource(resource)
            return wrapper

        return decorator

    async def run(self, *args, **kwargs) -> None:
        """Run the FlashMCP server."""
        await self._mcp_server.run(*args, **kwargs)

    @classmethod
    async def run_stdio(cls, app: "FlashMCP") -> None:
        """Run the server using stdio transport."""
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app._mcp_server.create_initialization_options(),
            )

    @classmethod
    async def run_sse(
        cls,
        app: "FlashMCP",
    ) -> None:
        """Run the server using SSE transport."""
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route
        import uvicorn

        sse = SseServerTransport("/messages")

        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await app.run(
                    streams[0],
                    streams[1],
                    app._mcp_server.create_initialization_options(),
                )

        async def handle_messages(request):
            await sse.handle_post_message(request.scope, request.receive, request._send)

        starlette_app = Starlette(
            debug=app.settings.debug,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=handle_messages, methods=["POST"]),
            ],
        )

        uvicorn.run(
            starlette_app,
            host=app.settings.host,
            port=app.settings.port,
            log_level=app.settings.log_level,
        )
