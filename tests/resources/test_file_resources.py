import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from FlashMCP.resources import FileResource


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
def temp_dir_with_files():
    """Create a temporary directory with test files."""
    with TemporaryDirectory() as d:
        path = Path(d).resolve()
        # Create some test files
        (path / "file1.txt").write_text("content1")
        (path / "file2.txt").write_text("content2")
        (path / "subdir").mkdir()
        (path / "subdir/file3.txt").write_text("content3")
        (path / "test.json").write_text('{"key": "value"}')
        yield path


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
        assert str(resource.uri) == f"file://{temp_file}"
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

    async def test_file_resource_read_missing_file(self, temp_file: Path):
        """Test reading a non-existent file."""
        temp_file.unlink()
        resource = FileResource(
            uri=f"file://{temp_file}",
            name="test",
            path=temp_file,
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
