from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LOG_LEVEL = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """FlashMCP server settings.

    All settings can be configured via environment variables with the prefix FASTMCP_.
    For example, FASTMCP_DEBUG=true will set debug=True.
    """

    model_config: SettingsConfigDict = SettingsConfigDict(
        env_prefix="FASTMCP_",
        env_file=".env",
        extra="ignore",
    )

    debug: bool = False
    log_level: LOG_LEVEL = "INFO"

    # Client settings
    client_log_level: LOG_LEVEL | None = None
