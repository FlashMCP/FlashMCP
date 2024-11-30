"""Base classes and interfaces for FlashMCP resources."""

import abc
from typing import Union

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from FlashMCP.types import LaxAnyUrl


class Resource(BaseModel, abc.ABC):
    """Base class for all resources."""

    model_config = ConfigDict(validate_default=True)

    uri: LaxAnyUrl = Field(description="URI of the resource")
    name: str | None = Field(description="Name of the resource", default=None)
    description: str | None = Field(
        description="Description of the resource", default=None
    )
    mime_type: str = Field(
        default="text/plain",
        description="MIME type of the resource content",
        pattern=r"^[a-zA-Z0-9]+/[a-zA-Z0-9\-+.]+$",
    )

    @field_validator("name", mode="before")
    @classmethod
    def set_default_name(cls, name: str | None, info: ValidationInfo) -> str:
        """Set default name from URI if not provided."""
        if name:
            return name
        # Extract everything after the protocol (e.g., "desktop" from "resource://desktop")
        if uri := info.data.get("uri"):
            uri_str = str(uri)
            if "://" in uri_str:
                name = uri_str.split("://", 1)[1]
                if name:
                    return name
        raise ValueError("Either name or uri must be provided")

    @abc.abstractmethod
    async def read(self) -> Union[str, bytes]:
        """Read the resource content."""
        pass
