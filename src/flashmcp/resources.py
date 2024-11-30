import inspect
import pydantic.json
import abc
import asyncio
import json
import re
from pathlib import Path
from typing import Dict, Optional, Callable, Any, Union

import httpx
from pydantic import BaseModel, Field, TypeAdapter, validate_call, field_validator
from pydantic.networks import _BaseUrl

from .utilities.logging import get_logger

logger = get_logger(__name__)


class Resource(BaseModel, abc.ABC):
    """Base class for all resources."""

    uri: _BaseUrl = Field(description="URI of the resource")
    name: str = Field(description="Name of the resource", default=None)
    description: Optional[str] = Field(
        description="Description of the resource", default=None
    )
    mime_type: str = Field(
        default="text/plain",
        description="MIME type of the resource content",
        pattern=r"^[a-zA-Z0-9]+/[a-zA-Z0-9\-+.]+$",
    )

    @field_validator("name", mode="before")
    @classmethod
    def set_default_name(cls, name: str | None, info) -> str:
        """Set default name from URI if not provided."""
        if name:
            return name
        # Extract everything after the protocol (e.g., "desktop" from "resource://desktop")
        uri = info.data.get("uri")
        if uri:
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

    model_config = {
        "validate_default": True,
    }


class TextResource(Resource):
    """A resource that reads from a string."""

    text: str = Field(description="Text content of the resource")

    async def read(self) -> str:
        """Read the text content."""
        return self.text


class BinaryResource(Resource):
    """A resource that reads from bytes."""

    data: bytes = Field(description="Binary content of the resource")

    async def read(self) -> bytes:
        """Read the binary content."""
        return self.data


class FunctionResource(Resource):
    """A resource that defers data loading by wrapping a function.

    The function is only called when the resource is read, allowing for lazy loading
    of potentially expensive data. This is particularly useful when listing resources,
    as the function won't be called until the resource is actually accessed.

    The function can return:
    - str for text content (default)
    - bytes for binary content
    - other types will be converted to JSON
    """

    func: Callable[[], Any] = Field(exclude=True)

    async def read(self) -> Union[str, bytes]:
        """Read the resource by calling the wrapped function."""
        try:
            result = self.func()
            if isinstance(result, Resource):
                return await result.read()
            if isinstance(result, bytes):
                return result
            if isinstance(result, str):
                return result
            try:
                return json.dumps(result, default=pydantic.json.pydantic_encoder)
            except TypeError:
                # If JSON serialization fails, try str()
                return str(result)
        except Exception as e:
            raise ValueError(f"Error reading resource {self.uri}: {e}")


class FileResource(Resource):
    """A resource that reads from a file.

    Set is_binary=True to read file as binary data instead of text.
    """

    path: Path = Field(description="Path to the file")
    is_binary: bool = Field(
        default=False,
        description="Whether to read the file as binary data",
    )
    mime_type: str = Field(
        default="text/plain",
        description="MIME type of the resource content",
    )

    @field_validator("path")
    @classmethod
    def validate_absolute_path(cls, path: Path) -> Path:
        """Ensure path is absolute."""
        if not path.is_absolute():
            raise ValueError("Path must be absolute")
        return path

    async def read(self) -> Union[str, bytes]:
        """Read the file content."""
        try:
            if self.is_binary:
                return await asyncio.to_thread(self.path.read_bytes)
            return await asyncio.to_thread(self.path.read_text)
        except Exception as e:
            raise ValueError(f"Error reading file {self.path}: {e}")


class HttpResource(Resource):
    """A resource that reads from an HTTP endpoint."""

    url: str = Field(description="URL to fetch content from")
    mime_type: Optional[str] = Field(
        default="application/json", description="MIME type of the resource content"
    )

    async def read(self) -> Union[str, bytes]:
        """Read the HTTP content."""
        async with httpx.AsyncClient() as client:
            response = await client.get(self.url)
            response.raise_for_status()
            return response.text


class DirectoryResource(Resource):
    """A resource that lists files in a directory."""

    path: Path = Field(description="Path to the directory")
    recursive: bool = Field(
        default=False, description="Whether to list files recursively"
    )
    pattern: Optional[str] = Field(
        default=None, description="Optional glob pattern to filter files"
    )
    mime_type: Optional[str] = Field(
        default="application/json", description="MIME type of the resource content"
    )

    @field_validator("path")
    @classmethod
    def validate_absolute_path(cls, path: Path) -> Path:
        """Ensure path is absolute."""
        if not path.is_absolute():
            raise ValueError("Path must be absolute")
        return path

    def list_files(self) -> list[Path]:
        """List files in the directory."""
        if not self.path.exists():
            raise FileNotFoundError(f"Directory not found: {self.path}")
        if not self.path.is_dir():
            raise NotADirectoryError(f"Not a directory: {self.path}")

        try:
            if self.pattern:
                return (
                    list(self.path.glob(self.pattern))
                    if not self.recursive
                    else list(self.path.rglob(self.pattern))
                )
            return (
                list(self.path.glob("*"))
                if not self.recursive
                else list(self.path.rglob("*"))
            )
        except Exception as e:
            raise ValueError(f"Error listing directory {self.path}: {e}")

    async def read(self) -> str:  # Always returns JSON string
        """Read the directory listing."""
        try:
            files = await asyncio.to_thread(self.list_files)
            file_list = [str(f.relative_to(self.path)) for f in files if f.is_file()]
            return json.dumps({"files": file_list}, indent=2)
        except Exception as e:
            raise ValueError(f"Error reading directory {self.path}: {e}")


class ResourceTemplate(BaseModel):
    """A template for dynamically creating resources."""

    uri_template: str = Field(
        description="URI template with parameters (e.g. weather://{city}/current)"
    )
    name: str = Field(description="Name of the resource")
    description: Optional[str] = Field(
        description="Description of what the resource does"
    )
    mime_type: str = Field(
        default="text/plain", description="MIME type of the resource content"
    )
    func: Callable = Field(exclude=True)
    parameters: dict = Field(description="JSON schema for function parameters")

    @classmethod
    def from_function(
        cls,
        func: Callable,
        uri_template: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> "ResourceTemplate":
        """Create a template from a function."""
        func_name = name or func.__name__
        if func_name == "<lambda>":
            raise ValueError("You must provide a name for lambda functions")

        # Get schema from TypeAdapter - will fail if function isn't properly typed
        parameters = TypeAdapter(func).json_schema()

        # ensure the arguments are properly cast
        func = validate_call(func)

        return cls(
            uri_template=uri_template,
            name=func_name,
            description=description or func.__doc__ or "",
            func=func,
            parameters=parameters,
        )

    def matches(self, uri: str) -> Optional[Dict[str, Any]]:
        """Check if URI matches template and extract parameters."""
        # Convert template to regex pattern
        pattern = self.uri_template.replace("{", "(?P<").replace("}", ">[^/]+)")
        match = re.match(f"^{pattern}$", uri)
        if match:
            return match.groupdict()
        return None

    async def create_resource(self, uri: str, params: Dict[str, Any]) -> Resource:
        """Create a resource from the template with the given parameters."""
        try:
            # Call function and check if result is a coroutine
            result = self.func(**params)
            if inspect.iscoroutine(result):
                result = await result

            return FunctionResource(
                uri=uri,
                name=self.name,
                description=self.description,
                func=lambda: result,  # Capture result in closure
            )
        except Exception as e:
            raise ValueError(f"Error creating resource from template: {e}")


class ResourceManager:
    """Manages FlashMCP resources."""

    def __init__(self, warn_on_duplicate_resources: bool = True):
        self._resources: Dict[str, Resource] = {}
        self._templates: Dict[str, ResourceTemplate] = {}
        self.warn_on_duplicate_resources = warn_on_duplicate_resources

    def add_template(
        self,
        func: Callable,
        uri_template: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> ResourceTemplate:
        """Add a template from a function."""
        template = ResourceTemplate.from_function(
            func,
            uri_template=uri_template,
            name=name,
            description=description,
            mime_type=mime_type,
        )
        self._templates[template.uri_template] = template
        return template

    async def get_resource(self, uri: Union[_BaseUrl, str]) -> Optional[Resource]:
        """Get resource by URI, checking concrete resources first, then templates."""
        uri_str = str(uri)
        logger.debug("Getting resource", extra={"uri": uri_str})

        # First check concrete resources
        if resource := self._resources.get(uri_str):
            return resource

        # Then check templates
        for template in self._templates.values():
            if params := template.matches(uri_str):
                try:
                    return await template.create_resource(uri_str, params)
                except Exception as e:
                    raise ValueError(f"Error creating resource from template: {e}")

        raise ValueError(f"Unknown resource: {uri}")

    def list_resources(self) -> list[Resource]:
        """List all registered resources."""
        logger.debug("Listing resources", extra={"count": len(self._resources)})
        return list(self._resources.values())

    def add_resource(self, resource: Resource) -> Resource:
        """Add a resource to the manager.

        Args:
            resource: A Resource instance to add

        Returns:
            The added resource. If a resource with the same URI already exists,
            returns the existing resource.
        """
        logger.debug(
            "Adding resource",
            extra={
                "uri": resource.uri,
                "type": type(resource).__name__,
                "name": resource.name,
            },
        )
        existing = self._resources.get(str(resource.uri))
        if existing:
            if self.warn_on_duplicate_resources:
                logger.warning(f"Resource already exists: {resource.uri}")
            return existing
        self._resources[str(resource.uri)] = resource
        return resource
