"""Sample code for FlashMCP using MCPMixin."""

from FlashMCP import FlashMCP
from FlashMCP.contrib.bulk_tool_caller import BulkToolCaller

mcp = FlashMCP()


@mcp.tool()
def echo_tool(text: str) -> str:
    """Echo the input text"""
    return text


bulk_tool_caller = BulkToolCaller()

bulk_tool_caller.register_tools(mcp)
