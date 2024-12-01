"""Base classes and interfaces for FlashMCP resources."""

import abc
from typing import Annotated, Union

from pydantic import (
    AnyUrl,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    FileUrl,
    ValidationInfo,
    field_validator,
)
from pydantic.networks import _BaseUrl  # TODO: remove this once pydantic is updated


def maybe_cast_str_to_any_url(x) -> AnyUrl:
    if isinstance(x, FileUrl):
        return x
    elif isinstance(x, AnyUrl):
        return x
    elif isinstance(x, str):
        if x.startswith("file://"):
            return FileUrl(x)
        return AnyUrl(x)
    raise ValueError(f"Expected str or AnyUrl, got {type(x)}")


LaxAnyUrl = Annotated[_BaseUrl | str, BeforeValidator(maybe_cast_str_to_any_url)]


class Resource(BaseModel, abc.ABC):
    """Base class for all resources."""

    model_config = ConfigDict(validate_default=True)

    uri: LaxAnyUrl = Field(default=..., description="URI of the resource")
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
        if uri := info.data.get("uri"):
            return str(uri)
        raise ValueError("Either name or uri must be provided")

    @abc.abstractmethod
    async def read(self) -> Union[str, bytes]:
        """Read the resource content."""
        pass
