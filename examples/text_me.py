# /// script
# dependencies = ["FlashMCP"]

"""
FlashMCP Echo Server
"""

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from FlashMCP import FlashMCP


class SurgeSettings(BaseSettings):
    model_config: SettingsConfigDict = SettingsConfigDict(
        env_prefix="SURGE_", env_file=".env"
    )

    api_key: str
    account_id: str
    my_phone_number: str


# Create server
mcp = FlashMCP("Text Me")
surge_settings = SurgeSettings()  # type: ignore


@mcp.tool()
def text_me(text_content: str) -> str:
    """Send a text message to a phone number"""
    with httpx.Client() as client:
        response = client.post(
            "https://api.surgemsg.com/messages",
            headers={
                "Authorization": surge_settings.api_key,
                "Surge-Account": surge_settings.account_id,
                "Content-Type": "application/json",
            },
            json={
                "body": text_content,
                "conversation": {
                    "contact": {"phone_number": surge_settings.my_phone_number}
                },
            },
        )
        response.raise_for_status()
        return response.json()
