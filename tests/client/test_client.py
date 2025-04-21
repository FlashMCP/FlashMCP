from typing import cast
from typing_extensions import Unpack
from collections.abc import AsyncIterator
from mcp import ClientSession
import contextlib
from mcp.shared.memory import create_client_server_memory_streams

import pytest
from pydantic import AnyUrl

from FlashMCP.client import Client
from FlashMCP.client.transports import FlashMCPTransport, ClientTransport, SessionKwargs
from FlashMCP.server.server import FlashMCP


@pytest.fixture
def FlashMCP_server():
    """Fixture that creates a FlashMCP server with tools, resources, and prompts."""
    server = FlashMCP("TestServer")

    # Add a tool
    @server.tool()
    def greet(name: str) -> str:
        """Greet someone by name."""
        return f"Hello, {name}!"

    # Add a second tool
    @server.tool()
    def add(a: int, b: int) -> int:
        """Add two numbers together."""
        return a + b

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


@pytest.fixture
def tagged_resources_server():
    """Fixture that creates a FlashMCP server with tagged resources and templates."""
    server = FlashMCP("TaggedResourcesServer")

    # Add a resource with tags
    @server.resource(
        uri="data://tagged", tags={"test", "metadata"}, description="A tagged resource"
    )
    async def get_tagged_data():
        return {"type": "tagged_data"}

    # Add a resource template with tags
    @server.resource(
        uri="template://{id}",
        tags={"template", "parameterized"},
        description="A tagged template",
    )
    async def get_template_data(id: str):
        return {"id": id, "type": "template_data"}

    return server


async def test_list_tools(FlashMCP_server):
    """Test listing tools with InMemoryClient."""
    client = Client(transport=FlashMCPTransport(FlashMCP_server))

    async with client:
        result = await client.list_tools()

        # Check that our tools are available
        assert len(result) == 2
        assert set(tool.name for tool in result) == {"greet", "add"}


async def test_call_tool(FlashMCP_server):
    """Test calling a tool with InMemoryClient."""
    client = Client(transport=FlashMCPTransport(FlashMCP_server))

    async with client:
        result = await client.call_tool("greet", {"name": "World"})

        # The result content should contain our greeting
        content_str = str(result[0])
        assert "Hello, World!" in content_str


async def test_list_resources(FlashMCP_server):
    """Test listing resources with InMemoryClient."""
    client = Client(transport=FlashMCPTransport(FlashMCP_server))

    async with client:
        result = await client.list_resources()

        # Check that our resource is available
        assert len(result) == 1
        assert str(result[0].uri) == "data://users"


async def test_list_prompts(FlashMCP_server):
    """Test listing prompts with InMemoryClient."""
    client = Client(transport=FlashMCPTransport(FlashMCP_server))

    async with client:
        result = await client.list_prompts()

        # Check that our prompt is available
        assert len(result) == 1
        assert result[0].name == "welcome"


async def test_get_prompt(FlashMCP_server):
    """Test getting a prompt with InMemoryClient."""
    client = Client(transport=FlashMCPTransport(FlashMCP_server))

    async with client:
        result = await client.get_prompt("welcome", {"name": "Developer"})

        # The result should contain our welcome message
        result_str = str(result)
        assert "Welcome to FlashMCP, Developer!" in result_str


async def test_read_resource(FlashMCP_server):
    """Test reading a resource with InMemoryClient."""
    client = Client(transport=FlashMCPTransport(FlashMCP_server))

    async with client:
        # Use the URI from the resource we know exists in our server
        uri = cast(
            AnyUrl, "data://users"
        )  # Use cast for type hint only, the URI is valid
        result = await client.read_resource(uri)

        # The contents should include our user list
        contents_str = str(result[0])
        assert "Alice" in contents_str
        assert "Bob" in contents_str
        assert "Charlie" in contents_str


async def test_client_connection(FlashMCP_server):
    """Test that the client connects and disconnects properly."""
    client = Client(transport=FlashMCPTransport(FlashMCP_server))

    # Before connection
    assert not client.is_connected()

    # During connection
    async with client:
        assert client.is_connected()

    # After connection
    assert not client.is_connected()

async def test_client_nested_context_manager(FlashMCP_server):
    """Test that the client connects and disconnects once in nested context manager."""
    class MockTransport(ClientTransport):
        def __init__(self):
            self._connected = False

        @contextlib.asynccontextmanager
        async def connect_session(
            self, **session_kwargs: Unpack[SessionKwargs],
        ) -> AsyncIterator[ClientSession]:
            assert not self._connected, "Transport is connected multiple times"
            self._connected = True
            async with create_client_server_memory_streams() as (
                _,
                server_streams,
            ):
                yield ClientSession(*server_streams)

    client = Client(transport=MockTransport())

    # Before connection
    assert not client.is_connected()

    # During connection
    async with client:
        assert client.is_connected()

        async with client:
            assert client.is_connected()

    # After connection
    assert not client.is_connected()

async def test_resource_template(FlashMCP_server):
    """Test using a resource template with InMemoryClient."""
    client = Client(transport=FlashMCPTransport(FlashMCP_server))

    async with client:
        # First, list templates
        result = await client.list_resource_templates()

        # Check that our template is available
        assert len(result) == 1
        assert "data://user/{user_id}" in result[0].uriTemplate

        # Now use the template with a specific user_id
        uri = cast(AnyUrl, "data://user/123")
        result = await client.read_resource(uri)

        # Check the content matches what we expect for the provided user_id
        content_str = str(result[0])
        assert '"id": "123"' in content_str
        assert '"name": "User 123"' in content_str
        assert '"active": true' in content_str


async def test_mcp_resource_generation(FlashMCP_server):
    """Test that resources are properly generated in MCP format."""
    client = Client(transport=FlashMCPTransport(FlashMCP_server))

    async with client:
        resources = await client.list_resources()
        assert len(resources) == 1
        resource = resources[0]

        # Verify resource has correct MCP format
        assert hasattr(resource, "uri")
        assert hasattr(resource, "name")
        assert hasattr(resource, "description")
        assert str(resource.uri) == "data://users"


async def test_mcp_template_generation(FlashMCP_server):
    """Test that templates are properly generated in MCP format."""
    client = Client(transport=FlashMCPTransport(FlashMCP_server))

    async with client:
        templates = await client.list_resource_templates()
        assert len(templates) == 1
        template = templates[0]

        # Verify template has correct MCP format
        assert hasattr(template, "uriTemplate")
        assert hasattr(template, "name")
        assert hasattr(template, "description")
        assert "data://user/{user_id}" in template.uriTemplate


async def test_template_access_via_client(FlashMCP_server):
    """Test that templates can be accessed through a client."""
    client = Client(transport=FlashMCPTransport(FlashMCP_server))

    async with client:
        # Verify template works correctly when accessed
        uri = cast(AnyUrl, "data://user/456")
        result = await client.read_resource(uri)
        content_str = str(result[0])
        assert '"id": "456"' in content_str


async def test_tagged_resource_metadata(tagged_resources_server):
    """Test that resource metadata is preserved in MCP format."""
    client = Client(transport=FlashMCPTransport(tagged_resources_server))

    async with client:
        resources = await client.list_resources()
        assert len(resources) == 1
        resource = resources[0]

        # Verify resource metadata is preserved
        assert str(resource.uri) == "data://tagged"
        assert resource.description == "A tagged resource"


async def test_tagged_template_metadata(tagged_resources_server):
    """Test that template metadata is preserved in MCP format."""
    client = Client(transport=FlashMCPTransport(tagged_resources_server))

    async with client:
        templates = await client.list_resource_templates()
        assert len(templates) == 1
        template = templates[0]

        # Verify template metadata is preserved
        assert "template://{id}" in template.uriTemplate
        assert template.description == "A tagged template"


async def test_tagged_template_functionality(tagged_resources_server):
    """Test that tagged templates function correctly when accessed."""
    client = Client(transport=FlashMCPTransport(tagged_resources_server))

    async with client:
        # Verify template functionality
        uri = cast(AnyUrl, "template://123")
        result = await client.read_resource(uri)
        content_str = str(result[0])
        assert '"id": "123"' in content_str
        assert '"type": "template_data"' in content_str
