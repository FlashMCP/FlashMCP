# /// script
# dependencies = ["FlashMCP", "pyautogui", "Pillow"]
# ///

"""
FlashMCP Screenshot Example

Give Claude a tool to capture and view screenshots.
"""

import io

from FlashMCP import FlashMCP, Image

# Create server
mcp = FlashMCP("Screenshot Demo")


@mcp.tool()
def take_screenshot() -> Image:
    """Take a screenshot of the user's screen and return it as an image"""
    import pyautogui

    screenshot = pyautogui.screenshot()
    buffer = io.BytesIO()
    # if the file exceeds ~1MB, it will be rejected by Claude
    screenshot.convert("RGB").save(buffer, format="JPEG", quality=60, optimize=True)
    return Image(data=buffer.getvalue(), format="jpeg")


if __name__ == "__main__":
    mcp.run()
