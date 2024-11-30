import pytest
from FlashMCP.resources import ResourceTemplate, FunctionResource


class TestResourceTemplate:
    """Test ResourceTemplate functionality."""

    def test_template_from_function(self):
        """Test creating a template from a function."""

        def weather(city: str, units: str = "metric") -> str:
            return f"Weather in {city} ({units})"

        template = ResourceTemplate.from_function(
            fn=weather,
            uri_template="weather://{city}/current",
            name="weather",
            description="Get current weather",
        )

        assert template.name == "weather"
        assert template.uri_template == "weather://{city}/current"
        assert template.mime_type == "text/plain"
        assert "city" in template.parameters["properties"]

    def test_template_from_lambda_error(self):
        """Test error when creating template from lambda without name."""
        with pytest.raises(
            ValueError, match="You must provide a name for lambda functions"
        ):
            ResourceTemplate.from_function(
                fn=lambda x: x,
                uri_template="test://{x}",
            )

    def test_template_matches(self):
        """Test URI matching against template."""

        def dummy(x: str) -> str:
            return x

        template = ResourceTemplate.from_function(
            fn=dummy,
            uri_template="test://{x}/value",
            name="test",
        )

        # Test matching URI
        params = template.matches("test://hello/value")
        assert params == {"x": "hello"}

        # Test non-matching URI
        params = template.matches("test://hello/wrong")
        assert params is None

    async def test_create_text_resource(self):
        """Test creating a text resource from template."""

        def greet(name: str) -> str:
            return f"Hello, {name}!"

        template = ResourceTemplate.from_function(
            fn=greet,
            uri_template="greet://{name}",
            name="greeter",
        )

        resource = await template.create_resource(
            "greet://world",
            {"name": "world"},
        )

        assert isinstance(resource, FunctionResource)
        content = await resource.read()
        assert content == "Hello, world!"

    async def test_create_binary_resource(self):
        """Test creating a binary resource from template."""

        def get_bytes(value: str) -> bytes:
            return value.encode()

        template = ResourceTemplate.from_function(
            fn=get_bytes,
            uri_template="bytes://{value}",
            name="bytes",
        )

        resource = await template.create_resource(
            "bytes://test",
            {"value": "test"},
        )

        assert isinstance(resource, FunctionResource)
        content = await resource.read()
        assert content == b"test"

    async def test_json_conversion(self):
        """Test automatic JSON conversion of non-string/bytes results."""

        def get_data(key: str) -> dict:
            return {"key": key, "value": 123}

        template = ResourceTemplate.from_function(
            fn=get_data,
            uri_template="data://{key}",
            name="data",
        )

        resource = await template.create_resource(
            "data://test",
            {"key": "test"},
        )

        assert isinstance(resource, FunctionResource)
        content = await resource.read()
        assert '"key": "test"' in content
        assert '"value": 123' in content

    async def test_template_error(self):
        """Test error handling in template resource creation."""

        def failing_func(x: str) -> str:
            raise ValueError("Test error")

        template = ResourceTemplate.from_function(
            fn=failing_func,
            uri_template="fail://{x}",
            name="fail",
        )

        with pytest.raises(ValueError, match="Error creating resource from template"):
            await template.create_resource("fail://test", {"x": "test"})

    async def test_async_text_resource(self):
        """Test creating a text resource from async function."""

        async def greet(name: str) -> str:
            return f"Hello, {name}!"

        template = ResourceTemplate.from_function(
            fn=greet,
            uri_template="greet://{name}",
            name="greeter",
        )

        resource = await template.create_resource(
            "greet://world",
            {"name": "world"},
        )

        assert isinstance(resource, FunctionResource)
        content = await resource.read()
        assert content == "Hello, world!"

    async def test_async_binary_resource(self):
        """Test creating a binary resource from async function."""

        async def get_bytes(value: str) -> bytes:
            return value.encode()

        template = ResourceTemplate.from_function(
            fn=get_bytes,
            uri_template="bytes://{value}",
            name="bytes",
        )

        resource = await template.create_resource(
            "bytes://test",
            {"value": "test"},
        )

        assert isinstance(resource, FunctionResource)
        content = await resource.read()
        assert content == b"test"

    async def test_async_json_conversion(self):
        """Test automatic JSON conversion of async results."""

        async def get_data(key: str) -> dict:
            return {"key": key, "value": 123}

        template = ResourceTemplate.from_function(
            fn=get_data,
            uri_template="data://{key}",
            name="data",
        )

        resource = await template.create_resource(
            "data://test",
            {"key": "test"},
        )

        assert isinstance(resource, FunctionResource)
        content = await resource.read()
        assert '"key": "test"' in content
        assert '"value": 123' in content

    async def test_async_error(self):
        """Test error handling in async template."""

        async def failing_func(x: str) -> str:
            raise ValueError("Test error")

        template = ResourceTemplate.from_function(
            fn=failing_func,
            uri_template="fail://{x}",
            name="fail",
        )

        with pytest.raises(
            ValueError, match="Error creating resource from template: Test error"
        ):
            await template.create_resource("fail://test", {"x": "test"})

    async def test_sync_returning_coroutine(self):
        """Test sync function that returns a coroutine."""

        async def async_helper(name: str) -> str:
            return f"Hello, {name}!"

        def get_greeting(name: str) -> str:
            return async_helper(name)  # Returns coroutine

        template = ResourceTemplate.from_function(
            fn=get_greeting,
            uri_template="greet://{name}",
            name="greeter",
        )

        resource = await template.create_resource(
            "greet://world",
            {"name": "world"},
        )

        assert isinstance(resource, FunctionResource)
        content = await resource.read()
        assert content == "Hello, world!"
