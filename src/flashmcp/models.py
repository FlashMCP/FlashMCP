"""Pydantic models for FlashMCP."""

from typing import Callable, Optional, Type

from pydantic import BaseModel


class Tool(BaseModel):
    """Internal tool registration info."""

    model_config: dict = dict(arbitrary_types_allowed=True)

    func: Callable
    name: str
    description: str
    input_schema: dict
    is_async: bool
    pydantic_model: Optional[Type[BaseModel]] = None
