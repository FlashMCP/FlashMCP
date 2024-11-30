"""Tool management for FlashMCP."""

import inspect
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field, TypeAdapter, validate_call

from .exceptions import ToolError
from .utilities.logging import get_logger
import FlashMCP

if TYPE_CHECKING:
    from FlashMCP.server import Context

logger = get_logger(__name__)


class Tool(BaseModel):
    """Internal tool registration info."""

    func: Callable = Field(exclude=True)
    name: str = Field(description="Name of the tool")
    description: str = Field(description="Description of what the tool does")
    parameters: dict = Field(description="JSON schema for tool parameters")
    is_async: bool = Field(description="Whether the tool is async")
    context_kwarg: Optional[str] = Field(
        None, description="Name of the kwarg that should receive context"
    )

    @classmethod
    def from_function(
        cls,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        context_kwarg: Optional[str] = None,
    ) -> "Tool":
        """Create a Tool from a function."""
        func_name = name or func.__name__

        if func_name == "<lambda>":
            raise ValueError("You must provide a name for lambda functions")

        func_doc = description or func.__doc__ or ""
        is_async = inspect.iscoroutinefunction(func)

        # Get schema from TypeAdapter - will fail if function isn't properly typed
        parameters = TypeAdapter(func).json_schema()

        # Find context parameter if it exists
        if context_kwarg is None:
            sig = inspect.signature(func)
            for param_name, param in sig.parameters.items():
                if param.annotation is FlashMCP.Context:
                    context_kwarg = param_name
                    break

        # ensure the arguments are properly cast
        func = validate_call(func)

        return cls(
            func=func,
            name=func_name,
            description=func_doc,
            parameters=parameters,
            is_async=is_async,
            context_kwarg=context_kwarg,
        )

    async def run(self, arguments: dict, context: Optional["Context"] = None) -> Any:
        """Run the tool with arguments."""
        try:
            # Inject context if needed
            if self.context_kwarg and context:
                arguments[self.context_kwarg] = context

            # Call function with proper async handling
            if self.is_async:
                return await self.func(**arguments)
            return self.func(**arguments)
        except Exception as e:
            raise ToolError(f"Error executing tool {self.name}: {e}") from e


class ToolManager:
    """Manages FlashMCP tools."""

    def __init__(self, warn_on_duplicate_tools: bool = True):
        self._tools: Dict[str, Tool] = {}
        self.warn_on_duplicate_tools = warn_on_duplicate_tools

    def get_tool(self, name: str) -> Optional[Tool]:
        """Get tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def add_tool(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Tool:
        """Add a tool to the server."""
        tool = Tool.from_function(func, name=name, description=description)
        existing = self._tools.get(tool.name)
        if existing:
            if self.warn_on_duplicate_tools:
                logger.warning(f"Tool already exists: {tool.name}")
            return existing
        self._tools[tool.name] = tool
        return tool

    async def call_tool(
        self, name: str, arguments: dict, context: Optional["Context"] = None
    ) -> Any:
        """Call a tool by name with arguments."""
        tool = self.get_tool(name)
        if not tool:
            raise ToolError(f"Unknown tool: {name}")

        return await tool.run(arguments, context=context)
