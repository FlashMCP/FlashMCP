from contextlib import ExitStack
from types import ModuleType
from typing import Any

from typing_extensions import Self

from FlashMCP import FlashMCP


def _get_agent_framework_module() -> ModuleType:
    try:
        import marvin
    except ImportError:
        raise ImportError(
            "please install `FlashMCP[chat]` to use TestClient with chat tools"
        )
    return marvin


class TestClient:
    def __init__(self, server: FlashMCP, agent_options: dict[str, Any] | None = None):
        self.server = server
        self._agent_framework = _get_agent_framework_module()
        self._agent_options = agent_options or {}
        self._stack = ExitStack()

    async def __aenter__(self) -> Self:
        self._stack.enter_context(self._agent_framework.Thread())
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass

    async def say(self, message: str) -> None:
        await self._agent_framework.Agent(
            mcp_servers=[self.server], **self._agent_options
        ).run_async(message)
