from typing import TYPE_CHECKING, Any, Dict

import mcp.server.FlashMCP
import mcp.types

from FlashMCP.prompts.prompt_manager import PromptManager
from FlashMCP.resources.resource_manager import ResourceManager
from FlashMCP.server.context import Context
from FlashMCP.tools.tool_manager import ToolManager
from FlashMCP.utilities.logging import get_logger

if TYPE_CHECKING:
    from FlashMCP.clients.base import BaseClient

    from .proxy import FlashMCPProxy

logger = get_logger(__name__)


class FlashMCP(mcp.server.FlashMCP.FlashMCP):
    def __init__(self, name: str | None = None, **settings: Any):
        # First initialize with default settings
        super().__init__(name=name or "FlashMCP", **settings)

        # Replace the default managers with our extended ones
        self._tool_manager = ToolManager(
            warn_on_duplicate_tools=self.settings.warn_on_duplicate_tools
        )
        self._resource_manager = ResourceManager(
            warn_on_duplicate_resources=self.settings.warn_on_duplicate_resources
        )
        self._prompt_manager = PromptManager(
            warn_on_duplicate_prompts=self.settings.warn_on_duplicate_prompts
        )

        # Setup for mounted apps
        self._mounted_apps: Dict[str, "FlashMCP"] = {}

    def get_context(self) -> Context:
        """
        Returns a Context object. Note that the context will only be valid
        during a request; outside a request, most methods will error.
        """
        try:
            request_context = self._mcp_server.request_context
        except LookupError:
            request_context = None
        return Context(request_context=request_context, FlashMCP=self)

    def mount(self, prefix: str, app: "FlashMCP") -> None:
        """Mount another FlashMCP application with a given prefix.

        When an application is mounted:
        - The tools are imported with prefixed names
          Example: If app has a tool named "get_weather", it will be available as "weather/get_weather"
        - The resources are imported with prefixed URIs
          Example: If app has a resource with URI "weather://forecast", it will be available as "weather+weather://forecast"
        - The templates are imported with prefixed URI templates
          Example: If app has a template with URI "weather://location/{id}", it will be available as "weather+weather://location/{id}"
        - The prompts are imported with prefixed names
          Example: If app has a prompt named "weather_prompt", it will be available as "weather/weather_prompt"

        Args:
            prefix: The prefix to use for the mounted application
            app: The FlashMCP application to mount
        """
        # Mount the app in the list of mounted apps
        self._mounted_apps[prefix] = app

        # Import tools from the mounted app with / delimiter
        tool_prefix = f"{prefix}/"
        self._tool_manager.import_tools(app._tool_manager, tool_prefix)

        # Import resources and templates from the mounted app with + delimiter
        resource_prefix = f"{prefix}+"
        self._resource_manager.import_resources(app._resource_manager, resource_prefix)
        self._resource_manager.import_templates(app._resource_manager, resource_prefix)

        # Import prompts with / delimiter
        prompt_prefix = f"{prefix}/"
        self._prompt_manager.import_prompts(app._prompt_manager, prompt_prefix)

        logger.info(f"Mounted app with prefix '{prefix}'")
        logger.debug(f"Imported tools with prefix '{tool_prefix}'")
        logger.debug(f"Imported resources with prefix '{resource_prefix}'")
        logger.debug(f"Imported templates with prefix '{resource_prefix}'")
        logger.debug(f"Imported prompts with prefix '{prompt_prefix}'")

    @classmethod
    async def as_proxy(cls, client: "BaseClient", **settings: Any) -> "FlashMCPProxy":
        """
        Create a FlashMCP proxy server from a client.

        This method creates a new FlashMCP server instance that proxies requests to the provided client.
        It discovers the client's tools, resources, prompts, and templates, and creates corresponding
        components in the server that forward requests to the client.

        Args:
            client: The client to proxy requests to
            **settings: Additional settings for the FlashMCP server

        Returns:
            A FlashMCP server that proxies requests to the client
        """
        from .proxy import FlashMCPProxy

        return await FlashMCPProxy.from_client(client=client, **settings)
