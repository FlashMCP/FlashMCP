"""Base classes for FlashMCP prompts."""

from __future__ import annotations as _annotations

import inspect
import json
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Annotated, Any, get_origin

import pydantic_core
from mcp.types import EmbeddedResource, ImageContent, PromptMessage, Role, TextContent
from mcp.types import Prompt as MCPPrompt
from mcp.types import PromptArgument as MCPPromptArgument
from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    PrivateAttr,
    TypeAdapter,
    validate_call,
)

from FlashMCP.server.dependencies import get_context
from FlashMCP.utilities.json_schema import compress_schema
from FlashMCP.utilities.logging import get_logger
from FlashMCP.utilities.types import (
    _convert_set_defaults,
    find_kwarg_by_type,
    get_cached_typeadapter,
)

if TYPE_CHECKING:
    pass

CONTENT_TYPES = TextContent | ImageContent | EmbeddedResource

logger = get_logger(__name__)


def Message(
    content: str | CONTENT_TYPES, role: Role | None = None, **kwargs: Any
) -> PromptMessage:
    """A user-friendly constructor for PromptMessage."""
    if isinstance(content, str):
        content = TextContent(type="text", text=content)
    if role is None:
        role = "user"
    return PromptMessage(content=content, role=role, **kwargs)


message_validator = TypeAdapter[PromptMessage](PromptMessage)

SyncPromptResult = (
    str
    | PromptMessage
    | dict[str, Any]
    | Sequence[str | PromptMessage | dict[str, Any]]
)
PromptResult = SyncPromptResult | Awaitable[SyncPromptResult]


class PromptArgument(BaseModel):
    """An argument that can be passed to a prompt."""

    name: str = Field(description="Name of the argument")
    description: str | None = Field(
        None, description="Description of what the argument does"
    )
    required: bool = Field(
        default=False, description="Whether the argument is required"
    )


class Prompt(BaseModel):
    """A prompt template that can be rendered with parameters."""

    name: str = Field(description="Name of the prompt")
    description: str | None = Field(
        None, description="Description of what the prompt does"
    )
    tags: Annotated[set[str], BeforeValidator(_convert_set_defaults)] = Field(
        default_factory=set, description="Tags for the prompt"
    )
    arguments: list[PromptArgument] | None = Field(
        None, description="Arguments that can be passed to the prompt"
    )
    fn: Callable[..., PromptResult | Awaitable[PromptResult]]
    _original_param_types: dict[str, Any] = PrivateAttr(default_factory=dict)

    @classmethod
    def from_function(
        cls,
        fn: Callable[..., PromptResult | Awaitable[PromptResult]],
        name: str | None = None,
        description: str | None = None,
        tags: set[str] | None = None,
    ) -> Prompt:
        """Create a Prompt from a function.

        The function can return:
        - A string (converted to a message)
        - A Message object
        - A dict (converted to a message)
        - A sequence of any of the above
        """
        from FlashMCP.server.context import Context

        original_fn_for_signature = fn
        func_name = name or original_fn_for_signature.__name__

        if func_name == "<lambda>":
            raise ValueError("You must provide a name for lambda functions")
            # Reject functions with *args or **kwargs
        sig = inspect.signature(original_fn_for_signature)
        for param in sig.parameters.values():
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                raise ValueError("Functions with *args are not supported as prompts")
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                raise ValueError("Functions with **kwargs are not supported as prompts")

        type_adapter = get_cached_typeadapter(original_fn_for_signature)
        parameters = type_adapter.json_schema()

        # Auto-detect context parameter if not provided

        context_kwarg = find_kwarg_by_type(
            original_fn_for_signature, kwarg_type=Context
        )
        if context_kwarg:
            prune_params = [context_kwarg]
        else:
            prune_params = None

        parameters = compress_schema(parameters, prune_params=prune_params)

        # Convert parameters to PromptArguments
        arguments: list[PromptArgument] = []
        if "properties" in parameters:
            for param_name, param in parameters["properties"].items():
                arguments.append(
                    PromptArgument(
                        name=param_name,
                        description=param.get("description"),
                        required=param_name in parameters.get("required", []),
                    )
                )

        # ensure the arguments are properly cast by Pydantic's validate_call
        validated_fn = validate_call(original_fn_for_signature)

        # Store original parameter types
        original_param_types_dict = {
            p.name: p.annotation
            for p in sig.parameters.values()
            if p.annotation != inspect.Parameter.empty
        }

        instance = cls(
            name=func_name,
            description=description or original_fn_for_signature.__doc__,
            arguments=arguments,
            fn=validated_fn,
            tags=tags or set(),
        )
        instance._original_param_types = original_param_types_dict
        return instance

    async def render(
        self,
        arguments: dict[str, Any] | None = None,
    ) -> list[PromptMessage]:
        """Render the prompt with arguments."""
        from FlashMCP.server.context import Context

        # Validate required arguments
        if self.arguments:
            required = {arg.name for arg in self.arguments if arg.required}
            provided = set(arguments or {})
            missing = required - provided
            if missing:
                raise ValueError(f"Missing required arguments: {missing}")

        try:
            # Prepare arguments
            kwargs = arguments.copy() if arguments else {}

            # <<< NEW: Attempt to deserialize JSON strings for complex types >>>
            if self._original_param_types:
                for param_name, param_value in list(kwargs.items()):
                    if param_name in self._original_param_types and isinstance(
                        param_value, str
                    ):
                        target_type_hint = self._original_param_types[param_name]

                        # Determine the actual base type to check (e.g., list from list[float])
                        origin_type = get_origin(target_type_hint)
                        # Fallback to the hint itself if no origin (e.g. for non-generic BaseModel)
                        type_to_check_for_complex = (
                            origin_type if origin_type else target_type_hint
                        )

                        is_json_candidate = False
                        if type_to_check_for_complex in (list, dict):
                            is_json_candidate = True
                        elif inspect.isclass(type_to_check_for_complex) and issubclass(
                            type_to_check_for_complex, BaseModel
                        ):
                            # BaseModel itself is imported from pydantic, so this check is fine
                            is_json_candidate = True

                        if is_json_candidate:
                            try:
                                kwargs[param_name] = json.loads(param_value)
                                logger.debug(
                                    f"FlashMCP: Auto-deserialized JSON string for param '{param_name}' in prompt '{self.name}'."
                                )
                            except json.JSONDecodeError:
                                # Not valid JSON, pass the original string to Pydantic validation
                                logger.debug(
                                    f"FlashMCP: Param '{param_name}' for prompt '{self.name}' is a string "
                                    "but not valid JSON. Passing as string to Pydantic validation."
                                )
            # <<< END NEW LOGIC >>>

            # Prepare arguments with context
            context_kwarg = find_kwarg_by_type(self.fn, kwarg_type=Context)
            if context_kwarg and context_kwarg not in kwargs:
                kwargs[context_kwarg] = get_context()

            # Call function and check if result is a coroutine
            result = self.fn(**kwargs)
            if inspect.iscoroutine(result):
                result = await result

            # Validate messages
            if not isinstance(result, list | tuple):
                result = [result]

            # Convert result to messages
            messages: list[PromptMessage] = []
            for msg in result:
                try:
                    if isinstance(msg, PromptMessage):
                        messages.append(msg)
                    elif isinstance(msg, str):
                        messages.append(
                            PromptMessage(
                                role="user",
                                content=TextContent(type="text", text=msg),
                            )
                        )
                    else:
                        content = pydantic_core.to_json(
                            msg, fallback=str, indent=2
                        ).decode()
                        messages.append(
                            PromptMessage(
                                role="user",
                                content=TextContent(type="text", text=content),
                            )
                        )
                except Exception:
                    raise ValueError("Could not convert prompt result to message.")

            return messages
        except Exception as e:
            logger.exception(f"Error rendering prompt {self.name}: {e}")
            raise ValueError(f"Error rendering prompt {self.name}.")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Prompt):
            return False
        return self.model_dump() == other.model_dump()

    def to_mcp_prompt(self, **overrides: Any) -> MCPPrompt:
        """Convert the prompt to an MCP prompt."""
        arguments = [
            MCPPromptArgument(
                name=arg.name,
                description=arg.description,
                required=arg.required,
            )
            for arg in self.arguments or []
        ]
        kwargs = {
            "name": self.name,
            "description": self.description,
            "arguments": arguments,
        }
        return MCPPrompt(**kwargs | overrides)
