"""Sample code for FlashMCP using MCPMixin."""

from contrib.bulk_tool_caller import BulkToolCaller
from FlashMCP import FlashMCP

mcp = FlashMCP()


@mcp.tool()
def echo_tool(text: str) -> str:
    """Echo the input text"""
    return text


bulk_tool_caller = BulkToolCaller()

bulk_tool_caller.register_tools(mcp)
