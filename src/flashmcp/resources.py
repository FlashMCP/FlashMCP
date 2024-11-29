"""Resource management for FlashMCP."""

import abc
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Optional

import httpx
from pydantic import BaseModel, field_validator


logger = logging.getLogger("mcp")


class Resource(BaseModel):
    """Base class for all resources."""

    uri: str
    name: str
    description: Optional[str] = None
    mime_type: str = "text/plain"

    @abc.abstractmethod
    async def read(self) -> str:
        """Read the resource content."""
        ...


class FileResource(Resource):
    """A file resource."""

    path: Path

    @field_validator("path")
    @classmethod
    def validate_absolute_path(cls, path: Path) -> Path:
        """Ensure path is absolute."""
        if not path.is_absolute():
            raise ValueError(f"Path must be absolute: {path}")
        return path

    async def read(self) -> str:
        """Read the file content."""
        try:
            return await asyncio.to_thread(self.path.read_text)
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {self.path}")
        except PermissionError:
            raise PermissionError(f"Permission denied: {self.path}")
        except Exception as e:
            raise ValueError(f"Error reading file {self.path}: {e}")


class HttpResource(Resource):
    """An HTTP resource."""

    url: str
    headers: Optional[Dict[str, str]] = None

    async def read(self) -> str:
        """Read the HTTP resource content."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.url, headers=self.headers)
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as e:
            raise ValueError(f"HTTP error {e.response.status_code}: {e}")
        except httpx.RequestError as e:
            raise ValueError(f"Request failed: {e}")


class DirectoryResource(Resource):
    """A directory resource."""

    path: Path
    recursive: bool = False
    pattern: Optional[str] = None
    mime_type: str = "application/json"

    @field_validator("path")
    @classmethod
    def validate_absolute_path(cls, path: Path) -> Path:
        """Ensure path is absolute."""
        if not path.is_absolute():
            raise ValueError(f"Path must be absolute: {path}")
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

    async def read(self) -> str:
        """Read the directory listing."""
        try:
            files = await asyncio.to_thread(self.list_files)
            file_list = [str(f.relative_to(self.path)) for f in files if f.is_file()]
            return json.dumps({"files": file_list}, indent=2)
        except Exception as e:
            raise ValueError(f"Error reading directory {self.path}: {e}")


class ResourceManager:
    """Manages FlashMCP resources."""

    def __init__(self):
        self._resources: Dict[str, Resource] = {}

    def get_resource(self, uri: str) -> Optional[Resource]:
        """Get resource by URI."""
        logger.debug("Getting resource", extra={"uri": uri})
        resource = self._resources.get(uri)
        if not resource:
            raise ValueError(f"Unknown resource: {uri}")
        return resource

    def list_resources(self) -> list[Resource]:
        """List all registered resources."""
        logger.debug("Listing resources", extra={"count": len(self._resources)})
        return list(self._resources.values())

    def add_file_resource(
        self,
        path: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> FileResource:
        """Add a file as a resource.

        Args:
            path: Absolute path to the file
            name: Optional name for the resource
            description: Optional description of the resource
            mime_type: Optional MIME type for the resource

        Returns:
            The created resource

        Raises:
            ValueError: If the path is not absolute or the file does not exist
        """
        logger.debug(
            "Adding file resource",
            extra={
                "path": path,
                "name": name,
                "mime_type": mime_type,
            },
        )
        file = Path(path)
        if not file.is_absolute():
            raise ValueError(f"Path must be absolute: {path}")
        if not file.is_file():
            raise FileNotFoundError(f"File does not exist: {path}")

        resource = FileResource(
            uri=f"file://{str(file)}",
            name=name or file.name,
            description=description,
            mime_type=mime_type or "text/plain",
            path=file,
        )
        self._resources[resource.uri] = resource
        return resource

    def add_http_resource(
        self,
        url: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> HttpResource:
        """Add an HTTP endpoint as a resource."""
        logger.debug(
            "Adding HTTP resource",
            extra={
                "url": url,
                "name": name,
                "mime_type": mime_type,
            },
        )
        resource = HttpResource(
            uri=f"http://{url}",
            name=name or url.split("/")[-1],
            description=description,
            mime_type=mime_type or "text/plain",
            url=url,
            headers=headers,
        )
        self._resources[resource.uri] = resource
        return resource

    def add_dir_resource(
        self,
        path: str,
        *,
        recursive: bool = False,
        pattern: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> DirectoryResource:
        """Add a directory as a resource."""
        logger.debug(
            "Adding directory resource",
            extra={
                "path": path,
                "recursive": recursive,
                "pattern": pattern,
                "name": name,
            },
        )
        dir_path = Path(path).expanduser().resolve()
        if not dir_path.is_dir():
            raise ValueError(f"Directory does not exist: {path}")

        resource = DirectoryResource(
            uri=f"dir://{str(dir_path)}",
            name=name or dir_path.name,
            description=description,
            path=dir_path,
            recursive=recursive,
            pattern=pattern,
        )
        self._resources[resource.uri] = resource
        return resource
