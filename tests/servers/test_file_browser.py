import json
from FlashMCP import FlashMCP
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def test_dir(tmp_path_factory) -> Path:
    """Create a temporary directory with test files."""
    tmp = tmp_path_factory.mktemp("test_files")

    # Create test files
    (tmp / "example.py").write_text("print('hello world')")
    (tmp / "readme.md").write_text("# Test Directory\nThis is a test.")
    (tmp / "config.json").write_text('{"test": true}')

    return tmp


@pytest.fixture
def mcp(test_dir: Path) -> FlashMCP:
    mcp = FlashMCP()

    @mcp.resource("fs://test_dir")
    def list_files() -> list[str]:
        """List the files in the test directory"""
        return [str(f) for f in test_dir.iterdir()]

    return mcp


async def test_list_resources(mcp: FlashMCP):
    resources = await mcp.list_resources()
    assert len(resources) == 1
    assert str(resources[0].uri) == "fs://test_dir"
    assert resources[0].name == "test_dir"


async def test_read_resource(mcp: FlashMCP):
    files = await mcp.read_resource("fs://test_dir")
    files = json.loads(files)

    assert isinstance(files, list)
    assert len(files) == 3
    assert any("example.py" in f for f in files)
    assert any("readme.md" in f for f in files)
    assert any("config.json" in f for f in files)
