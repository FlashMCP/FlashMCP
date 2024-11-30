"""
FlashMCP Echo Server
"""

from FlashMCP import FlashMCP


# Create server
mcp = FlashMCP("Echo Server")


@mcp.tool()
def echo(text: str) -> str:
    """Echo the input text"""
    return text


if __name__ == "__main__":
    mcp.run()
