"""FlashMCP - A more ergonomic interface for MCP servers."""

import base64
import json
import logging
from typing import Any, Callable, Dict, Optional, Sequence, Union

from mcp.server import Server as MCPServer
from mcp.server.stdio import stdio_server
from mcp.types import Resource as MCPResource
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from pydantic import BaseModel

from .exceptions import ResourceError
from .resources import ResourceManager
from .tools import ToolManager

logger = logging.getLogger("mcp")


class FlashMCPServer:
    def __init__(self, name: str):
        self._mcp_server = MCPServer(name)
        self._tool_manager = ToolManager()
        self._resource_manager = ResourceManager()
        self._setup_handlers()

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

    def add_file_resource(
        self,
        path: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> None:
        """Add a file as a resource."""
        self._resource_manager.add_file_resource(
            path,
            name=name,
            description=description,
            mime_type=mime_type,
        )

    def add_http_resource(
        self,
        url: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Add an HTTP endpoint as a resource."""
        self._resource_manager.add_http_resource(
            url,
            name=name,
            description=description,
            mime_type=mime_type,
            headers=headers,
        )

    def add_dir_resource(
        self,
        path: str,
        *,
        recursive: bool = False,
        pattern: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Add a directory as a resource."""
        self._resource_manager.add_dir_resource(
            path,
            recursive=recursive,
            pattern=pattern,
            name=name,
            description=description,
        )

    async def run(self, *args, **kwargs) -> None:
        """Run the FlashMCP server."""
        await self._mcp_server.run(*args, **kwargs)

    @classmethod
    async def run_stdio(cls, app: "FlashMCPServer") -> None:
        """Run the server using stdio transport."""
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app._mcp_server.create_initialization_options(),
            )

    @classmethod
    async def run_sse(
        cls, app: "FlashMCPServer", host: str = "0.0.0.0", port: int = 8000
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
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=handle_messages, methods=["POST"]),
            ],
        )

        uvicorn.run(starlette_app, host=host, port=port)
