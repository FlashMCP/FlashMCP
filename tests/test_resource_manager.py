"""Tests for resource management."""

import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from FlashMCP.resources import FileResource, ResourceManager


@pytest.fixture
def resource_manager():
    """Create a resource manager for testing."""
    return ResourceManager()


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


class TestResourceManager:
    """Test ResourceManager functionality."""

    def test_add_file_resource(
        self, resource_manager: ResourceManager, temp_file: Path
    ):
        """Test adding a file resource."""
        resource = resource_manager.add_file_resource(
            str(temp_file),
            name="test",
            description="test file",
            mime_type="text/plain",
        )
        assert isinstance(resource, FileResource)
        assert resource.uri == f"file://{temp_file}"
        assert resource.name == "test"
        assert resource.description == "test file"
        assert resource.mime_type == "text/plain"
        assert resource.path == temp_file

    def test_add_file_resource_relative_path_error(
        self, resource_manager: ResourceManager
    ):
        """Test ResourceManager rejects relative paths."""
        with pytest.raises(ValueError, match="Path must be absolute"):
            resource_manager.add_file_resource("test.txt")

    def test_add_file_resource_missing_file_error(
        self, resource_manager: ResourceManager, temp_dir: Path
    ):
        """Test ResourceManager rejects non-existent files."""
        missing_file = temp_dir / "missing.txt"
        with pytest.raises(FileNotFoundError):
            resource_manager.add_file_resource(str(missing_file))

    def test_get_resource_unknown_uri(self, resource_manager: ResourceManager):
        """Test getting a non-existent resource."""
        with pytest.raises(ValueError, match="Unknown resource"):
            resource_manager.get_resource("file://unknown")

    def test_get_resource(self, resource_manager: ResourceManager, temp_file: Path):
        """Test getting a resource by URI."""
        added = resource_manager.add_file_resource(str(temp_file))
        retrieved = resource_manager.get_resource(added.uri)
        assert retrieved == added

    def test_list_resources(self, resource_manager: ResourceManager, temp_file: Path):
        """Test listing all resources."""
        resource = resource_manager.add_file_resource(str(temp_file))
        resources = resource_manager.list_resources()
        assert len(resources) == 1
        assert resources[0] == resource

    async def test_resource_read_through_manager(
        self, resource_manager: ResourceManager, temp_file: Path
    ):
        """Test reading a resource through the manager."""
        resource = resource_manager.add_file_resource(str(temp_file))
        retrieved = resource_manager.get_resource(resource.uri)
        assert retrieved is not None
        content = await retrieved.read()
        assert content == "test content"

    async def test_resource_read_error_through_manager(
        self, resource_manager: ResourceManager, temp_file_no_cleanup: Path
    ):
        """Test error handling when reading through manager."""
        # Create resource while file exists
        resource = resource_manager.add_file_resource(str(temp_file_no_cleanup))
        retrieved = resource_manager.get_resource(resource.uri)
        assert retrieved is not None

        # Delete file and verify read fails
        temp_file_no_cleanup.unlink()
        with pytest.raises(FileNotFoundError):
            await retrieved.read()
