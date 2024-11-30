import pytest
from FlashMCP.resources import Resource, FunctionResource


class TestResourceValidation:
    """Test base Resource validation."""

    def test_resource_uri_validation(self):
        """Test URI validation."""

        def dummy_func() -> str:
            return "data"

        # Valid URI
        resource = FunctionResource(
            uri="http://example.com/data",
            name="test",
            func=dummy_func,
        )
        assert str(resource.uri) == "http://example.com/data"

        # Missing protocol
        with pytest.raises(ValueError, match="Input should be a valid URL"):
            FunctionResource(
                uri="invalid",
                name="test",
                func=dummy_func,
            )

        # Missing host
        with pytest.raises(ValueError, match="Input should be a valid URL"):
            FunctionResource(
                uri="http://",
                name="test",
                func=dummy_func,
            )

    def test_resource_name_from_uri(self):
        """Test name is extracted from URI if not provided."""

        def dummy_func() -> str:
            return "data"

        resource = FunctionResource(
            uri="resource://my-resource",
            func=dummy_func,
        )
        assert resource.name == "my-resource"

    def test_resource_name_validation(self):
        """Test name validation."""

        def dummy_func() -> str:
            return "data"

        # Must provide either name or URI
        with pytest.raises(ValueError, match="Either name or uri must be provided"):
            FunctionResource(
                func=dummy_func,
            )

        # Explicit name takes precedence over URI
        resource = FunctionResource(
            uri="resource://uri-name",
            name="explicit-name",
            func=dummy_func,
        )
        assert resource.name == "explicit-name"

    def test_resource_mime_type(self):
        """Test mime type handling."""

        def dummy_func() -> str:
            return "data"

        # Default mime type
        resource = FunctionResource(
            uri="resource://test",
            func=dummy_func,
        )
        assert resource.mime_type == "text/plain"

        # Custom mime type
        resource = FunctionResource(
            uri="resource://test",
            func=dummy_func,
            mime_type="application/json",
        )
        assert resource.mime_type == "application/json"

    async def test_resource_read_abstract(self):
        """Test that Resource.read() is abstract."""

        class ConcreteResource(Resource):
            pass

        with pytest.raises(TypeError, match="abstract method"):
            ConcreteResource(uri="test://test", name="test")
