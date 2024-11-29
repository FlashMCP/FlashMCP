import warnings
import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from FlashMCP.resources import FileResource, FunctionResource, ResourceManager


@pytest.fixture
def temp_file():
    """Create a temporary file for testing.

    File is automatically cleaned up after the test if it still exists.
    """
    content = "test content"
    with NamedTemporaryFile(mode="w", delete=False) as f:
        f.write(content)
        path = Path(f.name).resolve()
    yield path
    try:
        path.unlink()
    except FileNotFoundError:
        pass  # File was already deleted by the test


@pytest.fixture
def temp_file_no_cleanup():
    """Create a temporary file for testing.

    File is NOT automatically cleaned up - tests must handle cleanup.
    """
    content = "test content"
    with NamedTemporaryFile(mode="w", delete=False) as f:
        f.write(content)
        path = Path(f.name).resolve()
    return path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with TemporaryDirectory() as d:
        yield Path(d).resolve()


class TestFileResource:
    """Test FileResource functionality."""

    def test_file_resource_creation(self, temp_file: Path):
        """Test creating a FileResource."""
        resource = FileResource(
            uri=f"file://{temp_file}",
            name="test",
            description="test file",
            mime_type="text/plain",
            path=temp_file,
        )
        assert resource.uri == f"file://{temp_file}"
        assert resource.name == "test"
        assert resource.description == "test file"
        assert resource.mime_type == "text/plain"
        assert resource.path == temp_file

    def test_file_resource_relative_path_error(self):
        """Test FileResource rejects relative paths."""
        with pytest.raises(ValueError, match="Path must be absolute"):
            FileResource(
                uri="file://test.txt",
                name="test",
                path=Path("test.txt"),
            )

    def test_file_resource_str_path_conversion(self, temp_file: Path):
        """Test FileResource handles string paths."""
        resource = FileResource(
            uri=f"file://{temp_file}",
            name="test",
            path=str(temp_file),
        )
        assert isinstance(resource.path, Path)
        assert resource.path.is_absolute()

    async def test_file_resource_read(self, temp_file: Path):
        """Test reading a FileResource."""
        resource = FileResource(
            uri=f"file://{temp_file}",
            name="test",
            path=temp_file,
        )
        content = await resource.read()
        assert content == "test content"

    async def test_file_resource_read_missing_file(self, temp_dir: Path):
        """Test reading a non-existent file."""
        missing_file = temp_dir / "missing.txt"
        resource = FileResource(
            uri=f"file://{missing_file}",
            name="test",
            path=missing_file,
        )
        with pytest.raises(FileNotFoundError):
            await resource.read()

    async def test_file_resource_read_permission_error(self, temp_file: Path):
        """Test reading a file without permissions."""
        temp_file.chmod(0o000)  # Remove all permissions
        try:
            resource = FileResource(
                uri=f"file://{temp_file}",
                name="test",
                path=temp_file,
            )
            with pytest.raises(PermissionError):
                await resource.read()
        finally:
            temp_file.chmod(0o644)  # Restore permissions


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
        assert resource.uri == "fn://test"
        assert resource.name == "test"
        assert resource.description == "test function"
        assert resource.mime_type == "text/plain"
        assert resource.func == my_func

    def test_function_resource_invalid_uri(self):
        """Test FunctionResource rejects invalid URIs."""

        def my_func() -> str:
            return "test"

        with pytest.raises(ValueError, match="URI must start with fn://"):
            FunctionResource(
                uri="invalid://test",
                name="test",
                func=my_func,
            )

    async def test_function_resource_read_no_params(self):
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

    async def test_function_resource_read_with_params(self):
        """Test reading a FunctionResource with query parameters."""

        def my_func(x: str, y: str) -> str:
            return f"x={x}, y={y}"

        resource = FunctionResource(
            uri="fn://test?x=1&y=2",
            name="test",
            func=my_func,
        )
        content = await resource.read()
        assert content == "x=1, y=2"

    async def test_function_resource_read_returns_resource(self, temp_file: Path):
        """Test reading a FunctionResource that returns another Resource."""

        def my_func(name: str = "test") -> FileResource:
            return FileResource(
                uri=f"file://{temp_file}",
                name=name,
                path=temp_file,
            )

        resource = FunctionResource(
            uri="fn://test?name=example",
            name="test",
            func=my_func,
        )
        content = await resource.read()
        assert content == "test content"

    async def test_function_resource_read_error(self):
        """Test error handling when reading a FunctionResource."""

        def my_func(x: str) -> str:
            raise ValueError(f"test error: {x}")

        resource = FunctionResource(
            uri="fn://test?x=bad",
            name="test",
            func=my_func,
        )
        with pytest.raises(
            ValueError, match="Error calling function my_func: test error: bad"
        ):
            await resource.read()

    def test_parse_uri_params(self):
        """Test parsing URI parameters."""

        def my_func() -> str:
            return "test"

        resource = FunctionResource(
            uri="fn://test?x=1&y=hello&z=true",
            name="test",
            func=my_func,
        )
        params = resource._parse_uri_params()
        assert params == {
            "x": "1",
            "y": "hello",
            "z": "true",
        }

    def test_parse_uri_no_params(self):
        """Test parsing URI with no parameters."""

        def my_func() -> str:
            return "test"

        resource = FunctionResource(
            uri="fn://test",
            name="test",
            func=my_func,
        )
        params = resource._parse_uri_params()
        assert params == {}


class TestResourceManagerAdd:
    """Test ResourceManager add functionality."""

    def test_add_file_resource(self, temp_file: Path):
        """Test adding a file resource."""
        manager = ResourceManager()
        resource = FileResource(
            uri=f"file://{temp_file}",
            name="test",
            description="test file",
            mime_type="text/plain",
            path=temp_file,
        )
        added = manager.add_resource(resource)
        assert isinstance(added, FileResource)
        assert added.uri == f"file://{temp_file}"
        assert added.name == "test"
        assert added.description == "test file"
        assert added.mime_type == "text/plain"
        assert added.path == temp_file

    def test_add_file_resource_relative_path_error(self):
        """Test ResourceManager rejects relative paths."""
        with pytest.raises(ValueError, match="Path must be absolute"):
            FileResource(
                uri="file:///test.txt",
                name="test",
                path=Path("test.txt"),
            )

    def test_warn_on_duplicate_resources(self):
        """Test warning on duplicate resources."""
        manager = ResourceManager()
        resource = FileResource(
            uri="file:///test.txt",
            name="test",
            path=Path("/test.txt"),
        )
        manager.add_resource(resource)
        with pytest.warns(ResourceWarning):
            manager.add_resource(resource)

    def test_disable_warn_on_duplicate_resources(self):
        """Test disabling warning on duplicate resources."""
        manager = ResourceManager()
        resource = FileResource(
            uri="file:///test.txt",
            name="test",
            path=Path("/test.txt"),
        )
        manager.add_resource(resource)
        manager.warn_on_duplicate_resources = False
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            manager.add_resource(resource)


class TestResourceManagerRead:
    """Test ResourceManager read functionality."""

    def test_get_resource_unknown_uri(self):
        """Test getting a non-existent resource."""
        manager = ResourceManager()
        with pytest.raises(ValueError, match="Unknown resource"):
            manager.get_resource("file://unknown")

    def test_get_resource(self, temp_file: Path):
        """Test getting a resource by URI."""
        manager = ResourceManager()
        resource = FileResource(
            uri=f"file://{temp_file}",
            name="test",
            path=temp_file,
        )
        added = manager.add_resource(resource)
        retrieved = manager.get_resource(added.uri)
        assert retrieved == added

    async def test_resource_read_through_manager(self, temp_file: Path):
        """Test reading a resource through the manager."""
        manager = ResourceManager()
        resource = FileResource(
            uri=f"file://{temp_file}",
            name="test",
            path=temp_file,
        )
        added = manager.add_resource(resource)
        retrieved = manager.get_resource(added.uri)
        assert retrieved is not None
        content = await retrieved.read()
        assert content == "test content"

    async def test_resource_read_error_through_manager(
        self, temp_file_no_cleanup: Path
    ):
        """Test error handling when reading through manager."""
        manager = ResourceManager()
        # Create resource while file exists
        resource = FileResource(
            uri=f"file://{temp_file_no_cleanup}",
            name="test",
            path=temp_file_no_cleanup,
        )
        added = manager.add_resource(resource)
        retrieved = manager.get_resource(added.uri)
        assert retrieved is not None

        # Delete file and verify read fails
        temp_file_no_cleanup.unlink()
        with pytest.raises(FileNotFoundError):
            await retrieved.read()


class TestResourceManagerList:
    """Test ResourceManager list functionality."""

    def test_list_resources(self, temp_file: Path):
        """Test listing all resources."""
        manager = ResourceManager()
        resource = FileResource(
            uri=f"file://{temp_file}",
            name="test",
            path=temp_file,
        )
        added = manager.add_resource(resource)
        resources = manager.list_resources()
        assert len(resources) == 1
        assert resources[0] == added

    def test_list_resources_duplicate(self, temp_file: Path):
        """Test that adding the same resource twice only stores it once."""
        manager = ResourceManager()
        resource = FileResource(
            uri=f"file://{temp_file}",
            name="test",
            path=temp_file,
        )
        resource1 = manager.add_resource(resource)
        resource2 = manager.add_resource(resource)

        resources = manager.list_resources()
        assert len(resources) == 1
        assert resources[0] == resource1
        assert resource1 == resource2

    def test_list_multiple_resources(self, temp_file: Path, temp_file_no_cleanup: Path):
        """Test listing multiple different resources."""
        manager = ResourceManager()
        resource1 = FileResource(
            uri=f"file://{temp_file}",
            name="test1",
            path=temp_file,
        )
        resource2 = FileResource(
            uri=f"file://{temp_file_no_cleanup}",
            name="test2",
            path=temp_file_no_cleanup,
        )
        added1 = manager.add_resource(resource1)
        added2 = manager.add_resource(resource2)

        resources = manager.list_resources()
        assert len(resources) == 2
        assert resources[0] == added1
        assert resources[1] == added2
        assert added1 != added2
