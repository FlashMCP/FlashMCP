from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)
from FlashMCP import FlashMCP
import pytest


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

        @mcp.resource("data")
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
