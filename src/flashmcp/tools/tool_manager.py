import mcp.server.FlashMCP.tools
from mcp.server.FlashMCP.tools import Tool

from FlashMCP.utilities.logging import get_logger

logger = get_logger(__name__)


class ToolManager(mcp.server.FlashMCP.tools.ToolManager):
    """
    Extended ToolManager that supports importing tools from other managers.
    Adds ability to import tools from other managers with prefixed names.
    """

    def import_tools(
        self, tool_manager: "ToolManager", prefix: str | None = None
    ) -> None:
        """
        Import all tools from another ToolManager with prefixed names.

        Args:
            tool_manager: Another ToolManager instance to import tools from
            prefix: Prefix to add to tool names, including the delimiter.
                   The resulting tool name will be in the format "{prefix}{original_name}"
                   if prefix is provided, otherwise the original name is used.
                   For example, with prefix "weather/" and tool "forecast",
                   the imported tool would be available as "weather/forecast"
        """
        for name, tool in tool_manager._tools.items():
            prefixed_name = f"{prefix}{name}" if prefix else name

            # Create a shallow copy of the tool with the prefixed name
            copied_tool = Tool.from_function(
                tool.fn,
                name=prefixed_name,
                description=tool.description,
            )

            # Store the copied tool
            self._tools[prefixed_name] = copied_tool
            logger.debug(f"Imported tool: {name} as {prefixed_name}")
