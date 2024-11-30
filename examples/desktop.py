"""
FlashMCP Desktop Example

A simple example that exposes the desktop directory as a resource.
"""

from pathlib import Path

from FlashMCP.server import FlashMCP

# Create server
mcp = FlashMCP("Demo")


@mcp.resource("dir://desktop")
def desktop() -> list[str]:
    """List the files in the user's desktop"""
    desktop = Path.home() / "Desktop"
    return [str(f) for f in desktop.iterdir()]


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


if __name__ == "__main__":
    mcp.run()
