# /// script
# dependencies = ["pyautogui"]
# ///

"""
FlashMCP Screenshot Example

A simple example that provides a tool to capture screenshots.
"""

import base64
import io
import pyautogui

from FlashMCP.server import FlashMCP

# Create server
mcp = FlashMCP("Screenshot Demo")


@mcp.tool()
def take_screenshot() -> str:
    """Take a screenshot and return it as a base64 encoded string"""
    # Capture the screen
    screenshot = pyautogui.screenshot()

    # Convert to base64
    buffer = io.BytesIO()
    screenshot.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


if __name__ == "__main__":
    mcp.run()
