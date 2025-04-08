from typing import Any, cast

import mcp.types
from mcp.server.FlashMCP.prompts import Prompt
from mcp.server.FlashMCP.resources import Resource, ResourceTemplate
from mcp.server.FlashMCP.tools.base import Tool
from mcp.server.FlashMCP.utilities.func_metadata import func_metadata
from mcp.types import BlobResourceContents, PromptMessage, TextResourceContents

from FlashMCP.clients.base import BaseClient
from FlashMCP.server.context import Context
from FlashMCP.server.server import FlashMCP
from FlashMCP.utilities.logging import get_logger

logger = get_logger(__name__)


def _proxy_passthrough():
    pass


class ProxyTool(Tool):
    def __init__(self, client: "BaseClient", **kwargs):
        super().__init__(**kwargs)
        self._client = client

    @classmethod
    async def from_client(
        cls, client: "BaseClient", tool: mcp.types.Tool
    ) -> "ProxyTool":
        return cls(
            client=client,
            name=tool.name,
            description=tool.description,
            parameters=tool.inputSchema,
            fn=_proxy_passthrough,
            fn_metadata=func_metadata(_proxy_passthrough),
            is_async=True,
        )

    async def run(
        self, arguments: dict[str, Any], context: Context | None = None
    ) -> Any:
        async with self._client:
            result = await self._client.call_tool(self.name, arguments)
        if result.isError:
            raise ValueError(cast(mcp.types.TextContent, result.content[0]).text)
        return result.content[0]


class ProxyResource(Resource):
    def __init__(
        self, client: "BaseClient", *, _value: str | bytes | None = None, **kwargs
    ):
        super().__init__(**kwargs)
        self._client = client
        self._value = _value

    @classmethod
    async def from_client(
        cls, client: "BaseClient", resource: mcp.types.Resource
    ) -> "ProxyResource":
        return cls(
            client=client,
            uri=resource.uri,
            name=resource.name,
            description=resource.description,
            mime_type=resource.mimeType,
        )

    async def read(self) -> str | bytes:
        if self._value is not None:
            return self._value

        async with self._client:
            result = await self._client.read_resource(self.uri)
        if isinstance(result.contents[0], TextResourceContents):
            return result.contents[0].text
        elif isinstance(result.contents[0], BlobResourceContents):
            return result.contents[0].blob
        else:
            raise ValueError(f"Unsupported content type: {type(result.contents[0])}")


class ProxyTemplate(ResourceTemplate):
    def __init__(self, client: "BaseClient", **kwargs):
        super().__init__(**kwargs)
        self._client = client

    @classmethod
    async def from_client(
        cls, client: "BaseClient", template: mcp.types.ResourceTemplate
    ) -> "ProxyTemplate":
        return cls(
            client=client,
            uri_template=template.uriTemplate,
            name=template.name,
            description=template.description,
            fn=_proxy_passthrough,
            parameters={},
        )

    async def create_resource(self, uri: str, params: dict[str, Any]) -> ProxyResource:
        async with self._client:
            result = await self._client.read_resource(uri)

        if isinstance(result.contents[0], TextResourceContents):
            value = result.contents[0].text
        elif isinstance(result.contents[0], BlobResourceContents):
            value = result.contents[0].blob
        else:
            raise ValueError(f"Unsupported content type: {type(result.contents[0])}")

        return ProxyResource(
            client=self._client,
            uri=uri,
            name=self.name,
            description=self.description,
            mime_type=result.contents[0].mimeType,
            contents=result.contents,
            _value=value,
        )


class ProxyPrompt(Prompt):
    def __init__(self, client: "BaseClient", **kwargs):
        super().__init__(**kwargs)
        self._client = client

    @classmethod
    async def from_client(
        cls, client: "BaseClient", prompt: mcp.types.Prompt
    ) -> "ProxyPrompt":
        return cls(
            client=client,
            name=prompt.name,
            description=prompt.description,
            arguments=[a.model_dump() for a in prompt.arguments or []],
            fn=_proxy_passthrough,
        )

    async def render(self, arguments: dict[str, Any]) -> list[PromptMessage]:
        async with self._client:
            result = await self._client.get_prompt(self.name, arguments)
        return result.messages


class FlashMCPProxy(FlashMCP):
    def __init__(self, _async_constructor: bool, **kwargs):
        if not _async_constructor:
            raise ValueError(
                "FlashMCPProxy() was initialied unexpectedly. Please use a constructor like `FlashMCPProxy.from_client()` instead."
            )
        super().__init__(**kwargs)

    @classmethod
    async def from_client(
        cls, client: "BaseClient", name: str | None = None, **settings: Any
    ) -> "FlashMCPProxy":
        """Create a FlashMCP proxy server from a client.

        This method creates a new FlashMCP server instance that proxies requests to the provided client.
        It discovers the client's tools, resources, prompts, and templates, and creates corresponding
        components in the server that forward requests to the client.

        Args:
            client: The client to proxy requests to
            name: Optional name for the new FlashMCP server (defaults to client name if available)
            **settings: Additional settings for the FlashMCP server

        Returns:
            A FlashMCP server that proxies requests to the client
        """
        server = cls(name=name, **settings, _async_constructor=True)

        async with client:
            # Register proxies for client tools
            tools_result = await client.list_tools()
            for tool in tools_result.tools:
                tool_proxy = await ProxyTool.from_client(client, tool)
                server._tool_manager._tools[tool_proxy.name] = tool_proxy
                logger.debug(f"Created proxy for tool: {tool_proxy.name}")

            # Register proxies for client resources
            resources_result = await client.list_resources()
            for resource in resources_result.resources:
                resource_proxy = await ProxyResource.from_client(client, resource)
                server._resource_manager._resources[str(resource_proxy.uri)] = (
                    resource_proxy
                )
                logger.debug(f"Created proxy for resource: {resource_proxy.uri}")

            # Register proxies for client resource templates
            templates_result = await client.list_resource_templates()
            for template in templates_result.resourceTemplates:
                template_proxy = await ProxyTemplate.from_client(client, template)
                server._resource_manager._templates[template_proxy.uri_template] = (
                    template_proxy
                )
                logger.debug(
                    f"Created proxy for template: {template_proxy.uri_template}"
                )

            # Register proxies for client prompts
            prompts_result = await client.list_prompts()
            for prompt in prompts_result.prompts:
                prompt_proxy = await ProxyPrompt.from_client(client, prompt)
                server._prompt_manager._prompts[prompt_proxy.name] = prompt_proxy
                logger.debug(f"Created proxy for prompt: {prompt_proxy.name}")

            logger.info(f"Created server '{server.name}' proxying to client: {client}")
            return server
