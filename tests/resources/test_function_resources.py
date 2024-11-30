from FlashMCP.resources import FunctionResource


class TestFunctionResource:
    """Test FunctionResource functionality."""

    def test_function_resource_creation(self):
        """Test creating a FunctionResource."""

        def my_func(x: str = "") -> str:
            return f"Content: {x}"

        resource = FunctionResource(
            uri="fn://test",
            name="test",
            description="test function",
            mime_type="text/plain",
            func=my_func,
        )
        assert str(resource.uri) == "fn://test"
        assert resource.name == "test"
        assert resource.description == "test function"
        assert resource.mime_type == "text/plain"
        assert resource.func == my_func

    async def test_function_resource_read(self):
        """Test reading a FunctionResource with no parameters."""

        def my_func() -> str:
            return "test content"

        resource = FunctionResource(
            uri="fn://test",
            name="test",
            func=my_func,
        )
        content = await resource.read()
        assert content == "test content"
