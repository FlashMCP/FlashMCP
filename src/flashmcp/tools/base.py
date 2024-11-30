import FlashMCP
from FlashMCP.exceptions import ToolError


from pydantic import BaseModel, Field, TypeAdapter, validate_call


import inspect
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from FlashMCP.server import Context


class Tool(BaseModel):
    """Internal tool registration info."""

    fn: Callable = Field(exclude=True)
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
        fn: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        context_kwarg: Optional[str] = None,
    ) -> "Tool":
        """Create a Tool from a function."""
        func_name = name or fn.__name__

        if func_name == "<lambda>":
            raise ValueError("You must provide a name for lambda functions")

        func_doc = description or fn.__doc__ or ""
        is_async = inspect.iscoroutinefunction(fn)

        # Get schema from TypeAdapter - will fail if function isn't properly typed
        parameters = TypeAdapter(fn).json_schema()

        # Find context parameter if it exists
        if context_kwarg is None:
            sig = inspect.signature(fn)
            for param_name, param in sig.parameters.items():
                if param.annotation is FlashMCP.Context:
                    context_kwarg = param_name
                    break

        # ensure the arguments are properly cast
        fn = validate_call(fn)

        return cls(
            fn=fn,
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
                return await self.fn(**arguments)
            return self.fn(**arguments)
        except Exception as e:
            raise ToolError(f"Error executing tool {self.name}: {e}") from e
