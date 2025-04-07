from typing import cast

import pytest
from pydantic import AnyUrl

from FlashMCP.client.memory import InMemoryClient
from FlashMCP.server.server import FlashMCP


class _TestException(Exception):
    """Test exception for testing raise_exceptions behavior."""

    pass


@pytest.fixture
def FlashMCP_server():
    """Fixture that creates a FlashMCP server with tools, resources, and prompts."""
    server = FlashMCP("TestServer")

    # Add a tool
    @server.tool()
    def greet(name: str) -> str:
        """Greet someone by name."""
        return f"Hello, {name}!"

    # Add a tool that raises an exception
    @server.tool()
    def error_tool() -> str:
        """A tool that always raises an exception."""
        raise _TestException("Deliberate test exception")

    # Add a resource
    @server.resource(uri="data://users")
    async def get_users():
        return ["Alice", "Bob", "Charlie"]

    # Add a resource template
    @server.resource(uri="data://user/{user_id}")
    async def get_user(user_id: str):
        return {"id": user_id, "name": f"User {user_id}", "active": True}

    # Add a prompt
    @server.prompt()
    def welcome(name: str) -> str:
        return f"Welcome to FlashMCP, {name}!"

    return server


@pytest.mark.asyncio
async def test_list_tools(FlashMCP_server):
    """Test listing tools with InMemoryClient."""
    client = InMemoryClient(server=FlashMCP_server)

    async with client:
        result = await client.list_tools()

        # Check that our tools are available
        assert len(result.tools) == 2
        tool_names = [tool.name for tool in result.tools]
        assert "greet" in tool_names
        assert "error_tool" in tool_names


@pytest.mark.asyncio
async def test_call_tool(FlashMCP_server):
    """Test calling a tool with InMemoryClient."""
    client = InMemoryClient(server=FlashMCP_server)

    async with client:
        result = await client.call_tool("greet", {"name": "World"})

        # The result content should contain our greeting
        content_str = str(result.content[0])
        assert "Hello, World!" in content_str


@pytest.mark.asyncio
async def test_list_resources(FlashMCP_server):
    """Test listing resources with InMemoryClient."""
    client = InMemoryClient(server=FlashMCP_server)

    async with client:
        result = await client.list_resources()

        # Check that our resource is available
        assert len(result.resources) == 1
        assert str(result.resources[0].uri) == "data://users"


@pytest.mark.asyncio
async def test_list_prompts(FlashMCP_server):
    """Test listing prompts with InMemoryClient."""
    client = InMemoryClient(server=FlashMCP_server)

    async with client:
        result = await client.list_prompts()

        # Check that our prompt is available
        assert len(result.prompts) == 1
        assert result.prompts[0].name == "welcome"


@pytest.mark.asyncio
async def test_get_prompt(FlashMCP_server):
    """Test getting a prompt with InMemoryClient."""
    client = InMemoryClient(server=FlashMCP_server)

    async with client:
        result = await client.get_prompt("welcome", {"name": "Developer"})

        # The result should contain our welcome message
        result_str = str(result)
        assert "Welcome to FlashMCP, Developer!" in result_str


@pytest.mark.asyncio
async def test_read_resource(FlashMCP_server):
    """Test reading a resource with InMemoryClient."""
    client = InMemoryClient(server=FlashMCP_server)

    async with client:
        # Use the URI from the resource we know exists in our server
        uri = cast(
            AnyUrl, "data://users"
        )  # Use cast for type hint only, the URI is valid
        result = await client.read_resource(uri)

        # The contents should include our user list
        contents_str = str(result.contents[0])
        assert "Alice" in contents_str
        assert "Bob" in contents_str
        assert "Charlie" in contents_str


@pytest.mark.asyncio
async def test_client_connection(FlashMCP_server):
    """Test that the client connects and disconnects properly."""
    client = InMemoryClient(server=FlashMCP_server)

    # Before connection
    assert not client.is_connected()

    # During connection
    async with client:
        assert client.is_connected()

    # After connection
    assert not client.is_connected()


@pytest.mark.asyncio
async def test_resource_template(FlashMCP_server):
    """Test using a resource template with InMemoryClient."""
    client = InMemoryClient(server=FlashMCP_server)

    async with client:
        # First, list templates
        result = await client.list_resource_templates()

        # Check that our template is available
        assert len(result.resourceTemplates) == 1
        assert "data://user/{user_id}" in result.resourceTemplates[0].uriTemplate

        # Now use the template with a specific user_id
        uri = cast(AnyUrl, "data://user/123")
        result = await client.read_resource(uri)

        # Check the content matches what we expect for the provided user_id
        content_str = str(result.contents[0])
        assert '"id": "123"' in content_str
        assert '"name": "User 123"' in content_str
        assert '"active": true' in content_str
