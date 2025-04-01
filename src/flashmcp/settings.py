from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


from typing import Literal


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

    # Server settings
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # HTTP settings
    host: str = "0.0.0.0"
    port: int = 8000

    # resource settings
    warn_on_duplicate_resources: bool = True

    # tool settings
    warn_on_duplicate_tools: bool = True

    # prompt settings
    warn_on_duplicate_prompts: bool = True

    dependencies: list[str] = Field(
        default_factory=list,
        description="List of dependencies to install in the server environment",
    )
