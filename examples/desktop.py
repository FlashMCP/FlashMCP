"""
FlashMCP Desktop Example

A simple example that exposes the desktop directory as a resource.
"""

import asyncio
from pathlib import Path

from FlashMCP.server import FlashMCP

# Create server
mcp = FlashMCP("desktop")


@mcp.resource("desktop")
def desktop() -> list[str]:
    """List the files in the desktop directory"""
    desktop = Path.home() / "Desktop"
    return [str(f) for f in desktop.iterdir()]


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


if __name__ == "__main__":
    asyncio.run(FlashMCP.run_stdio(mcp))
