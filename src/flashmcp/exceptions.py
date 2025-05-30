"""Custom exceptions for FlashMCP."""

from mcp import McpError  # noqa: F401


class FlashMCPError(Exception):
    """Base error for FlashMCP."""


class ValidationError(FlashMCPError):
    """Error in validating parameters or return values."""


class ResourceError(FlashMCPError):
    """Error in resource operations."""


class ToolError(FlashMCPError):
    """Error in tool operations."""


class PromptError(FlashMCPError):
    """Error in prompt operations."""


class InvalidSignature(Exception):
    """Invalid signature for use with FlashMCP."""


class ClientError(Exception):
    """Error in client operations."""


class NotFoundError(Exception):
    """Object not found."""
