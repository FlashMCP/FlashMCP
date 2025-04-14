"""Custom exceptions for FlashMCP."""


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
