"""
FlashMCP Desktop Example

A simple example that exposes the desktop directory as a resource.
"""

import asyncio
from pathlib import Path

from FlashMCP.server import FlashMCPServer

# Create server
app = FlashMCPServer("desktop")

# Add desktop as a directory resource
desktop = Path.home() / "Desktop"
app.add_dir_resource(
    str(desktop),
    recursive=True,
    name="Desktop",
    description="Files on the desktop",
)


def main123():
    # Run the server
    asyncio.run(FlashMCPServer.run_stdio(app))


if __name__ == "__main__":
    main123()
