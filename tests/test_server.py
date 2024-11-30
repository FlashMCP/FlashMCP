from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)
from FlashMCP import FlashMCP
from FlashMCP.resources import FileResource, FunctionResource
from FlashMCP.tools import Image
from mcp.types import TextContent, ImageContent
import pytest
from pydantic import BaseModel
from pathlib import Path
import base64
from typing import Union


class TestServer:
    async def test_create_server(self):
        mcp = FlashMCP()
        assert mcp.name == "FlashMCP"

    async def test_add_tool_decorator(self):
        mcp = FlashMCP()

        @mcp.tool()
        def add(x: int, y: int) -> int:
            return x + y

        assert len(mcp._tool_manager.list_tools()) == 1

    async def test_add_tool_decorator_incorrect_usage(self):
        mcp = FlashMCP()

        with pytest.raises(TypeError, match="The @tool decorator was used incorrectly"):

            @mcp.tool  # Missing parentheses
            def add(x: int, y: int) -> int:
                return x + y

    async def test_add_resource_decorator(self):
        mcp = FlashMCP()

        @mcp.resource("r://data")
        def get_data(x: str) -> str:
            return f"Data: {x}"

        assert len(mcp._resource_manager.list_resources()) == 1

    async def test_add_resource_decorator_incorrect_usage(self):
        mcp = FlashMCP()

        with pytest.raises(
            TypeError, match="The @resource decorator was used incorrectly"
        ):

            @mcp.resource  # Missing parentheses
            def get_data(x: str) -> str:
                return f"Data: {x}"


def tool_fn(x: int, y: int) -> int:
    return x + y


def error_tool_fn() -> None:
    raise ValueError("Test error")


class ErrorResponse(BaseModel):
    is_error: bool = True
    message: str


def image_tool_fn(path: str) -> Image:
    return Image(path)


def mixed_content_tool_fn() -> list[Union[TextContent, ImageContent]]:
    return [
        TextContent(type="text", text="Hello"),
        ImageContent(type="image", data="abc", mimeType="image/png"),
    ]


class TestServerTools:
    async def test_add_tool(self):
        mcp = FlashMCP()
        mcp.add_tool(tool_fn)
        mcp.add_tool(tool_fn)
        assert len(mcp._tool_manager.list_tools()) == 1

    async def test_list_tools(self):
        mcp = FlashMCP()
        mcp.add_tool(tool_fn)
        async with client_session(mcp._mcp_server) as client:
            tools = await client.list_tools()
            assert len(tools.tools) == 1

    async def test_call_tool(self):
        mcp = FlashMCP()
        mcp.add_tool(tool_fn)
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool("my_tool", {"arg1": "value"})
            assert "error" not in result
            assert len(result.content) > 0

    async def test_tool_exception_handling(self):
        mcp = FlashMCP()
        mcp.add_tool(error_tool_fn)
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool("error_tool_fn", {})
            assert len(result.content) == 1
            assert result.content[0].type == "text"
            assert "Test error" in result.content[0].text
            assert result.content[0].is_error is True

    async def test_tool_exception_content(self):
        """Test that exception details are properly formatted in the response"""
        mcp = FlashMCP()
        mcp.add_tool(error_tool_fn)
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool("error_tool_fn", {})
            content = result.content[0]
            assert content.type == "text"
            assert isinstance(content.text, str)
            assert "Test error" in content.text
            assert content.is_error is True

    async def test_tool_text_conversion(self):
        mcp = FlashMCP()
        mcp.add_tool(tool_fn)
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool("tool_fn", {"x": 1, "y": 2})
            assert len(result.content) == 1
            assert result.content[0].type == "text"
            assert result.content[0].text == "3"

    async def test_tool_image_helper(self, tmp_path: Path):
        # Create a test image
        image_path = tmp_path / "test.png"
        image_path.write_bytes(b"fake png data")

        mcp = FlashMCP()
        mcp.add_tool(image_tool_fn)
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool("image_tool_fn", {"path": str(image_path)})
            assert len(result.content) == 1
            assert result.content[0].type == "image"
            assert result.content[0].mimeType == "image/png"
            # Verify base64 encoding
            decoded = base64.b64decode(result.content[0].data)
            assert decoded == b"fake png data"

    async def test_tool_mixed_content(self):
        mcp = FlashMCP()
        mcp.add_tool(mixed_content_tool_fn)
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool("mixed_content_tool_fn", {})
            assert len(result.content) == 2
            assert result.content[0].type == "text"
            assert result.content[0].text == "Hello"
            assert result.content[1].type == "image"
            assert result.content[1].mimeType == "image/png"
            assert result.content[1].data == "abc"


class TestServerResources:
    async def test_text_resource(self):
        mcp = FlashMCP()

        def get_text():
            return "Hello, world!"

        resource = FunctionResource(uri="resource://test", name="test", func=get_text)
        mcp.add_resource(resource)

        async with client_session(mcp._mcp_server) as client:
            result = await client.read_resource("resource://test")
            assert result.contents[0].text == "Hello, world!"

    async def test_binary_resource(self):
        mcp = FlashMCP()

        def get_binary():
            return b"Binary data"

        resource = FunctionResource(
            uri="resource://binary",
            name="binary",
            func=get_binary,
            is_binary=True,
            mime_type="application/octet-stream",
        )
        mcp.add_resource(resource)

        async with client_session(mcp._mcp_server) as client:
            result = await client.read_resource("resource://binary")
            assert result.contents[0].blob == base64.b64encode(b"Binary data").decode()

    async def test_file_resource_text(self, tmp_path: Path):
        mcp = FlashMCP()

        # Create a text file
        text_file = tmp_path / "test.txt"
        text_file.write_text("Hello from file!")

        resource = FileResource(uri="file://test.txt", name="test.txt", path=text_file)
        mcp.add_resource(resource)

        async with client_session(mcp._mcp_server) as client:
            result = await client.read_resource("file://test.txt")
            assert result.contents[0].text == "Hello from file!"

    async def test_file_resource_binary(self, tmp_path: Path):
        mcp = FlashMCP()

        # Create a binary file
        binary_file = tmp_path / "test.bin"
        binary_file.write_bytes(b"Binary file data")

        resource = FileResource(
            uri="file://test.bin",
            name="test.bin",
            path=binary_file,
            is_binary=True,
            mime_type="application/octet-stream",
        )
        mcp.add_resource(resource)

        async with client_session(mcp._mcp_server) as client:
            result = await client.read_resource("file://test.bin")
            assert (
                result.contents[0].blob
                == base64.b64encode(b"Binary file data").decode()
            )
