import warnings

import pytest
from pydantic import BaseModel

from FlashMCP.exceptions import ToolError
from FlashMCP.tools import ToolManager


class TestAddTools:
    def test_basic_function(self):
        """Test registering and running a basic function."""

        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        manager = ToolManager()
        manager.add_tool(add)

        tool = manager.get_tool("add")
        assert tool is not None
        assert tool.name == "add"
        assert tool.description == "Add two numbers."
        assert tool.is_async is False
        assert tool.parameters["properties"]["a"]["type"] == "integer"
        assert tool.parameters["properties"]["b"]["type"] == "integer"

    async def test_async_function(self):
        """Test registering and running an async function."""

        async def fetch_data(url: str) -> str:
            """Fetch data from URL."""
            return f"Data from {url}"

        manager = ToolManager()
        manager.add_tool(fetch_data)

        tool = manager.get_tool("fetch_data")
        assert tool is not None
        assert tool.name == "fetch_data"
        assert tool.description == "Fetch data from URL."
        assert tool.is_async is True
        assert tool.parameters["properties"]["url"]["type"] == "string"

    def test_pydantic_model_function(self):
        """Test registering a function that takes a Pydantic model."""

        class UserInput(BaseModel):
            name: str
            age: int

        def create_user(user: UserInput, flag: bool) -> dict:
            """Create a new user."""
            return {"id": 1, **user.model_dump()}

        manager = ToolManager()
        manager.add_tool(create_user)

        tool = manager.get_tool("create_user")
        assert tool is not None
        assert tool.name == "create_user"
        assert tool.description == "Create a new user."
        assert tool.is_async is False
        assert "name" in tool.parameters["$defs"]["UserInput"]["properties"]
        assert "age" in tool.parameters["$defs"]["UserInput"]["properties"]
        assert "flag" in tool.parameters["properties"]

    def test_add_invalid_tool(self):
        manager = ToolManager()
        with pytest.raises(AttributeError):
            manager.add_tool(1)

    def test_add_lambda(self):
        manager = ToolManager()
        manager.add_tool(lambda x: x)
        assert len(manager.list_tools()) == 1

    def test_warn_on_duplicate_tools(self):
        """Test warning on duplicate tools."""

        def f(x: int) -> int:
            return x

        manager = ToolManager()
        manager.add_tool(f)
        with pytest.warns(ResourceWarning):
            manager.add_tool(f)

    def test_disable_warn_on_duplicate_tools(self):
        """Test disabling warning on duplicate tools."""

        def f(x: int) -> int:
            return x

        manager = ToolManager()
        manager.add_tool(f)
        manager.warn_on_duplicate_tools = False
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            manager.add_tool(f)


class TestCallTools:
    async def test_call_tool(self):
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        manager = ToolManager()
        manager.add_tool(add)
        result = await manager.call_tool("add", {"a": 1, "b": 2})
        assert result == 3

    async def test_call_async_tool(self):
        async def double(n: int) -> int:
            """Double a number."""
            return n * 2

        manager = ToolManager()
        manager.add_tool(double)
        result = await manager.call_tool("double", {"n": 5})
        assert result == 10

    async def test_call_tool_with_default_args(self):
        def add(a: int, b: int = 1) -> int:
            """Add two numbers."""
            return a + b

        manager = ToolManager()
        manager.add_tool(add)
        result = await manager.call_tool("add", {"a": 1})
        assert result == 2

    async def test_call_tool_with_missing_args(self):
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        manager = ToolManager()
        manager.add_tool(add)
        with pytest.raises(ToolError):
            await manager.call_tool("add", {"a": 1})

    async def test_call_unknown_tool(self):
        manager = ToolManager()
        with pytest.raises(ToolError):
            await manager.call_tool("unknown", {"a": 1})
