import logging

from mcp.server.FlashMCP.prompts import PromptManager as BasePromptManager

logger = logging.getLogger(__name__)


class PromptManager(BasePromptManager):
    """
    Extended PromptManager that supports importing prompts from other managers.
    Adds ability to import prompts from other managers with prefixed names.
    """

    def import_prompts(
        self, manager: "PromptManager", prefix: str | None = None
    ) -> None:
        """
        Import all prompts from another PromptManager with prefixed names.

        Args:
            manager: Another PromptManager instance to import prompts from
            prefix: Prefix to add to prompt names. The resulting prompt name will
                   be in the format "{prefix}{original_name}" if prefix is provided,
                   otherwise the original name is used.
                   For example, with prefix "weather/" and prompt "forecast_prompt",
                   the imported prompt would be available as "weather/forecast_prompt"
        """
        for name, prompt in manager._prompts.items():
            # Create prefixed name - we keep the original name in the Prompt object
            prefixed_name = f"{prefix}{name}" if prefix else name

            # Log the import
            logger.debug(f"Importing prompt with name {name} as {prefixed_name}")

            # Store the prompt with the prefixed name
            self._prompts[prefixed_name] = prompt
