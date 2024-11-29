"""Tool management for FlashMCP."""

import inspect
from typing import Any, Callable, Dict, Optional, get_type_hints

from pydantic import BaseModel, create_model

from .exceptions import ToolError
from .models import Tool


class ToolManager:
    """Manages FlashMCP tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

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
    ) -> None:
        """Add a tool to the server."""
        func_name = name or func.__name__
        func_doc = description or func.__doc__ or ""
        is_async = inspect.iscoroutinefunction(func)

        # Get type hints for parameters
        hints = get_type_hints(func)
        if "return" in hints:
            del hints["return"]

        # Check for Pydantic model parameter
        if len(hints) == 1 and issubclass(next(iter(hints.values())), BaseModel):
            model = next(iter(hints.values()))
            schema = model.model_json_schema()
            pydantic_model = model
        else:
            # Create parameter schema from type hints
            fields = {}
            sig = inspect.signature(func)
            for param_name, param in sig.parameters.items():
                param_type = hints.get(param_name, Any)
                default = (
                    ... if param.default is inspect.Parameter.empty else param.default
                )
                fields[param_name] = (param_type, default)

            model = create_model(f"{func_name}Args", **fields)
            schema = model.model_json_schema()
            pydantic_model = model

        self._tools[func_name] = Tool(
            func=func,
            name=func_name,
            description=func_doc,
            input_schema=schema,
            is_async=is_async,
            pydantic_model=pydantic_model,
        )

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """Call a tool by name with arguments."""
        tool = self.get_tool(name)
        if not tool:
            raise ToolError(f"Unknown tool: {name}")

        try:
            # Validate arguments using schema
            if tool.pydantic_model:
                validated_args = tool.pydantic_model(**arguments)
                args_dict = validated_args.model_dump()
            else:
                args_dict = arguments

            # Call function with proper async handling
            if tool.is_async:
                return await tool.func(**args_dict)
            return tool.func(**args_dict)
        except Exception as e:
            raise ToolError(f"Error executing tool {name}: {e}") from e
