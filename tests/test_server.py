from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)
from FlashMCP.server import FlashMCPServer


class TestServer:
    async def test_create_server(self):
        server = FlashMCPServer()
        assert server.name == "FlashMCPServer"


class TestServerTools:
    async def test_add_tool(self):
        server = FlashMCPServer()
        server.add_tool(lambda x: x)
        assert len(server._tool_manager.list_tools()) == 1

    async def test_list_tools(self):
        server = FlashMCPServer()
        server.add_tool(lambda x: x)
        async with client_session(server._mcp_server) as client:
            tools = await client.list_tools()
            assert len(tools.tools) == 1

    async def test_call_tool(self):
        server = FlashMCPServer()
        server.add_tool(lambda x: x)
        async with client_session(server._mcp_server) as client:
            result = await client.call_tool("my_tool", {"arg1": "value"})
            assert "error" not in result
            assert len(result.content) > 0
