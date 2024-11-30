"""
FlashMCP Echo Server
"""

from FlashMCP import FlashMCP


# Create server
mcp = FlashMCP("Echo Server")


@mcp.tool()
def echo_tool(text: str) -> str:
    """Echo the input text"""
    return text


@mcp.resource("echo://{text}")
def echo_resource(text: str) -> str:
    """Echo the input text"""
    return f"Echo: {text}"


@mcp.prompt("echo")
def echo_prompt(text: str) -> str:
    return text


if __name__ == "__main__":
    mcp.run()
