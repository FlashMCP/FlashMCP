from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)
from FlashMCP import FlashMCP, Context
from FlashMCP.resources import FileResource, FunctionResource
from FlashMCP.utilities.types import Image
from mcp.types import TextContent, ImageContent
import pytest
from pydantic import BaseModel
from pathlib import Path
import base64
from typing import Union, TYPE_CHECKING

if TYPE_CHECKING:
    from FlashMCP import Context


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

        @mcp.resource("r://{x}")
        def get_data(x: str) -> str:
            return f"Data: {x}"

        assert len(mcp._resource_manager._templates) == 1

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

    async def test_tool_mixed_list_with_image(self, tmp_path: Path):
        """Test that lists containing Image objects and other types are handled correctly"""
        # Create a test image
        image_path = tmp_path / "test.png"
        image_path.write_bytes(b"test image data")

        def mixed_list_fn() -> list:
            return [
                "text message",
                Image(image_path),
                {"key": "value"},
                TextContent(type="text", text="direct content"),
            ]

        mcp = FlashMCP()
        mcp.add_tool(mixed_list_fn)
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool("mixed_list_fn", {})
            assert len(result.content) == 4
            # Check text conversion
            assert result.content[0].type == "text"
            assert '"text message"' in result.content[0].text
            # Check image conversion
            assert result.content[1].type == "image"
            assert result.content[1].mimeType == "image/png"
            assert base64.b64decode(result.content[1].data) == b"test image data"
            # Check dict conversion
            assert result.content[2].type == "text"
            assert '"key": "value"' in result.content[2].text
            # Check direct TextContent
            assert result.content[3].type == "text"
            assert result.content[3].text == "direct content"


class TestServerResources:
    async def test_text_resource(self):
        mcp = FlashMCP()

        def get_text():
            return "Hello, world!"

        resource = FunctionResource(uri="resource://test", name="test", fn=get_text)
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
            fn=get_binary,
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


class TestServerResourceTemplates:
    async def test_resource_with_params(self):
        """Test that a resource with function parameters raises an error if the URI
        parameters don't match"""
        mcp = FlashMCP()

        with pytest.raises(ValueError, match="Mismatch between URI parameters"):

            @mcp.resource("resource://data")
            def get_data(param: str) -> str:
                return f"Data: {param}"

    async def test_resource_with_uri_params(self):
        """Test that a resource with URI parameters is automatically a template"""
        mcp = FlashMCP()

        with pytest.raises(ValueError, match="Mismatch between URI parameters"):

            @mcp.resource("resource://{param}")
            def get_data() -> str:
                return "Data"

    async def test_resource_with_untyped_params(self):
        """Test that a resource with untyped parameters raises an error"""
        mcp = FlashMCP()

        @mcp.resource("resource://{param}")
        def get_data(param) -> str:
            return "Data"

    async def test_resource_matching_params(self):
        """Test that a resource with matching URI and function parameters works"""
        mcp = FlashMCP()

        @mcp.resource("resource://{name}/data")
        def get_data(name: str) -> str:
            return f"Data for {name}"

        async with client_session(mcp._mcp_server) as client:
            result = await client.read_resource("resource://test/data")
            assert result.contents[0].text == "Data for test"

    async def test_resource_mismatched_params(self):
        """Test that mismatched parameters raise an error"""
        mcp = FlashMCP()

        with pytest.raises(ValueError, match="Mismatch between URI parameters"):

            @mcp.resource("resource://{name}/data")
            def get_data(user: str) -> str:
                return f"Data for {user}"

    async def test_resource_multiple_params(self):
        """Test that multiple parameters work correctly"""
        mcp = FlashMCP()

        @mcp.resource("resource://{org}/{repo}/data")
        def get_data(org: str, repo: str) -> str:
            return f"Data for {org}/{repo}"

        async with client_session(mcp._mcp_server) as client:
            result = await client.read_resource("resource://cursor/FlashMCP/data")
            assert result.contents[0].text == "Data for cursor/FlashMCP"

    async def test_resource_multiple_mismatched_params(self):
        """Test that mismatched parameters raise an error"""
        mcp = FlashMCP()

        with pytest.raises(ValueError, match="Mismatch between URI parameters"):

            @mcp.resource("resource://{org}/{repo}/data")
            def get_data(org: str, repo_2: str) -> str:
                return f"Data for {org}"

        """Test that a resource with no parameters works as a regular resource"""
        mcp = FlashMCP()

        @mcp.resource("resource://static")
        def get_data() -> str:
            return "Static data"

        async with client_session(mcp._mcp_server) as client:
            result = await client.read_resource("resource://static")
            assert result.contents[0].text == "Static data"

    async def test_template_to_resource_conversion(self):
        """Test that templates are properly converted to resources when accessed"""
        mcp = FlashMCP()

        @mcp.resource("resource://{name}/data")
        def get_data(name: str) -> str:
            return f"Data for {name}"

        # Should be registered as a template
        assert len(mcp._resource_manager._templates) == 1
        assert len(await mcp.list_resources()) == 0

        # When accessed, should create a concrete resource
        resource = await mcp._resource_manager.get_resource("resource://test/data")
        assert isinstance(resource, FunctionResource)
        result = await resource.read()
        assert result == "Data for test"


class TestContextInjection:
    """Test context injection in tools."""

    async def test_context_detection(self):
        """Test that context parameters are properly detected."""
        mcp = FlashMCP()

        def tool_with_context(x: int, ctx: Context) -> str:
            return f"Request {ctx.request_id}: {x}"

        tool = mcp._tool_manager.add_tool(tool_with_context)
        assert tool.context_kwarg == "ctx"

    async def test_context_injection(self):
        """Test that context is properly injected into tool calls."""
        mcp = FlashMCP()

        def tool_with_context(x: int, ctx: Context) -> str:
            assert ctx.request_id is not None
            return f"Request {ctx.request_id}: {x}"

        mcp.add_tool(tool_with_context)
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool("tool_with_context", {"x": 42})
            assert len(result.content) == 1
            assert "Request" in result.content[0].text
            assert "42" in result.content[0].text

    async def test_async_context(self):
        """Test that context works in async functions."""
        mcp = FlashMCP()

        async def async_tool(x: int, ctx: Context) -> str:
            assert ctx.request_id is not None
            return f"Async request {ctx.request_id}: {x}"

        mcp.add_tool(async_tool)
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool("async_tool", {"x": 42})
            assert len(result.content) == 1
            assert "Async request" in result.content[0].text
            assert "42" in result.content[0].text

    async def test_context_logging(self):
        """Test that context logging methods work."""
        mcp = FlashMCP()

        def logging_tool(msg: str, ctx: Context) -> str:
            ctx.debug("Debug message")
            ctx.info("Info message")
            ctx.warning("Warning message")
            ctx.error("Error message")
            return f"Logged messages for {msg}"

        mcp.add_tool(logging_tool)
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool("logging_tool", {"msg": "test"})
            assert len(result.content) == 1
            assert "Logged messages for test" in result.content[0].text

    async def test_optional_context(self):
        """Test that context is optional."""
        mcp = FlashMCP()

        def no_context(x: int) -> int:
            return x * 2

        mcp.add_tool(no_context)
        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool("no_context", {"x": 21})
            assert len(result.content) == 1
            assert result.content[0].text == "42"

    async def test_context_resource_access(self):
        """Test that context can access resources."""
        mcp = FlashMCP()

        @mcp.resource("test://data")
        def test_resource() -> str:
            return "resource data"

        @mcp.tool()
        async def tool_with_resource(ctx: Context) -> str:
            data = await ctx.read_resource("test://data")
            return f"Read resource: {data}"

        async with client_session(mcp._mcp_server) as client:
            result = await client.call_tool("tool_with_resource", {})
            assert len(result.content) == 1
            assert "Read resource: resource data" in result.content[0].text
