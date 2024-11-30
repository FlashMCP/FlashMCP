import FlashMCP
from FlashMCP.exceptions import ToolError


from pydantic import BaseModel, Field, TypeAdapter, validate_call


import inspect
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from FlashMCP.server import Context


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
            if self.context_kwarg:
                arguments[self.context_kwarg] = context

            # Call function with proper async handling
            if self.is_async:
                return await self.func(**arguments)
            return self.func(**arguments)
        except Exception as e:
            raise ToolError(f"Error executing tool {self.name}: {e}") from e
