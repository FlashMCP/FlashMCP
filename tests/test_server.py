from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)
from FlashMCP import FlashMCP


class TestServer:
    async def test_create_server(self):
        mcp = FlashMCP()
        assert mcp.name == "FlashMCP"

    async def test_add_tool_decorator(self):
        mcp = FlashMCP()

        @mcp.tool
        def add(x: int, y: int) -> int:
            return x + y

        async with client_session(mcp._mcp_server) as client:
            tools = await client.list_tools()
            assert len(tools.tools) == 1
            assert tools.tools[0].name == "add"


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
