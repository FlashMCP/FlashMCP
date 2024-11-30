"""FlashMCP - A more ergonomic interface for MCP servers."""

import pydantic_core
from typing import Any, Literal, Optional, Union

from mcp.server import RequestContext
from pydantic import BaseModel
from pydantic.networks import AnyUrl

from FlashMCP.utilities.logging import get_logger
import asyncio
import functools
import json
from typing import Callable, Sequence
import inspect
import re

from mcp.server import Server as MCPServer
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport
from mcp.types import (
    Resource as MCPResource,
    Tool as MCPTool,
    ResourceTemplate as MCPResourceTemplate,
    TextContent,
    ImageContent,
)
from pydantic_settings import BaseSettings
from pydantic.networks import _BaseUrl

from FlashMCP.exceptions import ResourceError
from FlashMCP.resources import Resource, ResourceManager
from FlashMCP.resources.types import FunctionResource
from FlashMCP.tools import ToolManager
from FlashMCP.utilities.logging import configure_logging
from FlashMCP.utilities.types import Image

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

        # Set up MCP protocol handlers
        self._setup_handlers()

        # Configure logging
        configure_logging(self.settings.log_level)

    @property
    def name(self) -> str:
        return self._mcp_server.name

    def run(self, transport: Literal["stdio", "sse"] = "stdio") -> None:
        """Run the FlashMCP server. Note this is a synchronous function.

        Args:
            transport: Transport protocol to use ("stdio" or "sse")
        """
        TRANSPORTS = Literal["stdio", "sse"]
        if transport not in TRANSPORTS.__args__:  # type: ignore
            raise ValueError(f"Unknown transport: {transport}")

        if transport == "stdio":
            asyncio.run(self.run_stdio_async())
        else:  # transport == "sse"
            asyncio.run(self.run_sse_async())

    def _setup_handlers(self) -> None:
        """Set up core MCP protocol handlers."""
        self._mcp_server.list_tools()(self.list_tools)
        self._mcp_server.call_tool()(self.call_tool)
        self._mcp_server.list_resources()(self.list_resources)
        self._mcp_server.read_resource()(self.read_resource)
        # TODO: This has not been added to MCP yet, see https://github.com/jlowin/FlashMCP/issues/10
        # self._mcp_server.list_resource_templates()(self.list_resource_templates)

    async def list_tools(self) -> list[MCPTool]:
        """List all available tools."""
        tools = self._tool_manager.list_tools()
        return [
            MCPTool(
                name=info.name,
                description=info.description,
                inputSchema=info.parameters,
            )
            for info in tools
        ]

    def get_context(self) -> Optional["Context"]:
        try:
            request_context = self._mcp_server.request_context
            return Context(request_context=request_context, FlashMCP=self)
        except LookupError:
            return None

    async def call_tool(
        self, name: str, arguments: dict
    ) -> Sequence[Union[TextContent, ImageContent]]:
        """Call a tool by name with arguments."""
        try:
            context = self.get_context()
            result = await self._tool_manager.call_tool(
                name, arguments, context=context
            )
            return _convert_to_content(result)
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            return [
                TextContent(
                    type="text",
                    text=str(e),
                    is_error=True,
                )
            ]

    async def list_resources(self) -> list[MCPResource]:
        """List all available resources."""

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

    async def list_resource_templates(self) -> list[MCPResourceTemplate]:
        templates = self._resource_manager.list_templates()
        return [
            MCPResourceTemplate(
                uriTemplate=template.uri_template,
                name=template.name,
                description=template.description,
            )
            for template in templates
        ]

    async def read_resource(self, uri: _BaseUrl) -> Union[str, bytes]:
        """Read a resource by URI."""
        resource = await self._resource_manager.get_resource(uri)
        if not resource:
            raise ResourceError(f"Unknown resource: {uri}")

        try:
            return await resource.read()
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {e}")
            raise ResourceError(str(e))

    def add_tool(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """Add a tool to the server.

        The tool function can optionally request a Context object by adding a parameter
        with the Context type annotation. See the @tool decorator for examples.

        Args:
            func: The function to register as a tool
            name: Optional name for the tool (defaults to function name)
            description: Optional description of what the tool does
        """
        self._tool_manager.add_tool(func, name=name, description=description)

    def tool(
        self, name: Optional[str] = None, description: Optional[str] = None
    ) -> Callable:
        """Decorator to register a tool.

        Tools can optionally request a Context object by adding a parameter with the Context type annotation.
        The context provides access to MCP capabilities like logging, progress reporting, and resource access.

        Args:
            name: Optional name for the tool (defaults to function name)
            description: Optional description of what the tool does

        Example:
            @server.tool()
            def my_tool(x: int) -> str:
                return str(x)

            @server.tool()
            def tool_with_context(x: int, ctx: Context) -> str:
                ctx.info(f"Processing {x}")
                return str(x)

            @server.tool()
            async def async_tool(x: int, context: Context) -> str:
                await context.report_progress(50, 100)
                return str(x)
        """
        # Check if user passed function directly instead of calling decorator
        if callable(name):
            raise TypeError(
                "The @tool decorator was used incorrectly. "
                "Did you forget to call it? Use @tool() instead of @tool"
            )

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

    def resource(
        self,
        uri: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> Callable:
        """Decorator to register a function as a resource.

        The function will be called when the resource is read to generate its content.
        The function can return:
        - str for text content
        - bytes for binary content
        - other types will be converted to JSON

        If the URI contains parameters (e.g. "resource://{param}") or the function
        has parameters, it will be registered as a template resource.

        Args:
            uri: URI for the resource (e.g. "resource://my-resource" or "resource://{param}")
            name: Optional name for the resource
            description: Optional description of the resource
            mime_type: Optional MIME type for the resource

        Example:
            @server.resource("resource://my-resource")
            def get_data() -> str:
                return "Hello, world!"

            @server.resource("resource://{city}/weather")
            def get_weather(city: str) -> str:
                return f"Weather for {city}"
        """
        # Check if user passed function directly instead of calling decorator
        if callable(uri):
            raise TypeError(
                "The @resource decorator was used incorrectly. "
                "Did you forget to call it? Use @resource('uri') instead of @resource"
            )

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                return func(*args, **kwargs)

            # Check if this should be a template
            has_uri_params = "{" in uri and "}" in uri
            has_func_params = bool(inspect.signature(func).parameters)

            if has_uri_params or has_func_params:
                # Validate that URI params match function params
                uri_params = set(re.findall(r"{(\w+)}", uri))
                func_params = set(inspect.signature(func).parameters.keys())

                if uri_params != func_params:
                    raise ValueError(
                        f"Mismatch between URI parameters {uri_params} "
                        f"and function parameters {func_params}"
                    )

                # Register as template
                self._resource_manager.add_template(
                    wrapper,
                    uri_template=uri,
                    name=name,
                    description=description,
                    mime_type=mime_type or "text/plain",
                )
            else:
                # Register as regular resource
                resource = FunctionResource(
                    uri=uri,
                    name=name,
                    description=description,
                    mime_type=mime_type or "text/plain",
                    func=wrapper,
                )
                self.add_resource(resource)
            return wrapper

        return decorator

    async def run_stdio_async(self) -> None:
        """Run the server using stdio transport."""
        async with stdio_server() as (read_stream, write_stream):
            print(f'Starting "{self.name}"...')
            await self._mcp_server.run(
                read_stream,
                write_stream,
                self._mcp_server.create_initialization_options(),
            )

    async def run_sse_async(self) -> None:
        """Run the server using SSE transport."""
        from starlette.applications import Starlette
        from starlette.routing import Route
        import uvicorn

        sse = SseServerTransport("/messages")

        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await self._mcp_server.run(
                    streams[0],
                    streams[1],
                    self._mcp_server.create_initialization_options(),
                )

        async def handle_messages(request):
            await sse.handle_post_message(request.scope, request.receive, request._send)

        starlette_app = Starlette(
            debug=self.settings.debug,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=handle_messages, methods=["POST"]),
            ],
        )

        uvicorn.run(
            starlette_app,
            host=self.settings.host,
            port=self.settings.port,
            log_level=self.settings.log_level,
        )


def _convert_to_content(value: Any) -> Sequence[Union[TextContent, ImageContent]]:
    """Convert a tool result to MCP content types."""

    # Already a sequence of valid content types
    if isinstance(value, (list, tuple)):
        if all(isinstance(x, (TextContent, ImageContent)) for x in value):
            return value
        # Handle mixed content including Image objects
        result = []
        for item in value:
            if isinstance(item, (TextContent, ImageContent)):
                result.append(item)
            elif isinstance(item, Image):
                result.append(item.to_image_content())
            else:
                result.append(
                    TextContent(
                        type="text",
                        text=json.dumps(pydantic_core.to_jsonable_python(item)),
                    )
                )
        return result

    # Single content type
    if isinstance(value, (TextContent, ImageContent)):
        return [value]

    # Image helper
    if isinstance(value, Image):
        return [value.to_image_content()]

    # All other types - convert to JSON string with pydantic encoder
    return [
        TextContent(
            type="text",
            text=json.dumps(pydantic_core.to_jsonable_python(value)),
        )
    ]


class Context(BaseModel):
    """Context object providing access to MCP capabilities.

    This provides a cleaner interface to MCP's RequestContext functionality.
    It gets injected into tool and resource functions that request it via type hints.

    To use context in a tool function, add a parameter with the Context type annotation:

    ```python
    @server.tool()
    def my_tool(x: int, ctx: Context) -> str:
        # Log messages to the client
        ctx.info(f"Processing {x}")
        ctx.debug("Debug info")
        ctx.warning("Warning message")
        ctx.error("Error message")

        # Report progress
        ctx.report_progress(50, 100)

        # Access resources
        data = ctx.read_resource("resource://data")

        # Get request info
        request_id = ctx.request_id
        client_id = ctx.client_id

        return str(x)
    ```

    The context parameter name can be anything as long as it's annotated with Context.
    The context is optional - tools that don't need it can omit the parameter.
    """

    _request_context: RequestContext
    _FlashMCP: FlashMCP

    def __init__(
        self, *, request_context: RequestContext, FlashMCP: FlashMCP, **kwargs: Any
    ):
        super().__init__(**kwargs)
        self._request_context = request_context
        self._FlashMCP = FlashMCP

    @property
    def FlashMCP(self) -> FlashMCP:
        """Access to the FlashMCP server."""
        return self._FlashMCP

    @property
    def request_context(self) -> RequestContext:
        """Access to the underlying request context."""
        return self._request_context

    async def report_progress(
        self, progress: float, total: Optional[float] = None
    ) -> None:
        """Report progress for the current operation.

        Args:
            progress: Current progress value e.g. 24
            total: Optional total value e.g. 100
        """

        progress_token = (
            self.request_context.meta.progressToken
            if self.request_context.meta
            else None
        )

        if not progress_token:
            return

        await self.request_context.session.send_progress_notification(
            progress_token=progress_token, progress=progress, total=total
        )

    async def read_resource(self, uri: Union[str, AnyUrl]) -> Union[str, bytes]:
        """Read a resource by URI.

        Args:
            uri: Resource URI to read

        Returns:
            The resource content as either text or bytes
        """
        return await self._FlashMCP.read_resource(uri)

    def log(
        self,
        level: Literal["debug", "info", "warning", "error"],
        message: str,
        *,
        logger_name: Optional[str] = None,
    ) -> None:
        """Send a log message to the client.

        Args:
            level: Log level (debug, info, warning, error)
            message: Log message
            logger_name: Optional logger name
            **extra: Additional structured data to include
        """
        self.request_context.session.send_log_message(
            level=level, data=message, logger=logger_name
        )

    @property
    def client_id(self) -> Optional[str]:
        """Get the client ID if available."""
        return self.request_context.meta.clientId if self.request_context.meta else None

    @property
    def request_id(self) -> str:
        """Get the unique ID for this request."""
        return self.request_context.request_id

    @property
    def session(self):
        """Access to the underlying session for advanced usage."""
        return self.request_context.session

    # Convenience methods for common log levels
    def debug(self, message: str, **extra: Any) -> None:
        """Send a debug log message."""
        self.log("debug", message, **extra)

    def info(self, message: str, **extra: Any) -> None:
        """Send an info log message."""
        self.log("info", message, **extra)

    def warning(self, message: str, **extra: Any) -> None:
        """Send a warning log message."""
        self.log("warning", message, **extra)

    def error(self, message: str, **extra: Any) -> None:
        """Send an error log message."""
        self.log("error", message, **extra)
