from mcp.server.FlashMCP.prompts import Prompt
from mcp.server.FlashMCP.prompts.base import PromptArgument

from FlashMCP.prompts.prompt_manager import PromptManager


def test_import_prompts():
    """Test importing prompts from one manager to another with a prefix."""
    # Setup source manager with prompts
    source_manager = PromptManager()

    # Create test prompts with proper function handlers
    async def summary_fn(**kwargs):
        return [{"role": "assistant", "content": f"Summary of: {kwargs.get('text')}"}]

    async def translate_fn(**kwargs):
        return [
            {
                "role": "assistant",
                "content": f"Translation to {kwargs.get('language')}: {kwargs.get('text')}",
            }
        ]

    summary_prompt = Prompt(
        name="summary",
        description="Generate a summary of text",
        arguments=[PromptArgument(name="text", description="Text to summarize")],
        fn=summary_fn,
    )
    source_manager._prompts["summary"] = summary_prompt

    translate_prompt = Prompt(
        name="translate",
        description="Translate text to another language",
        arguments=[
            PromptArgument(name="text", description="Text to translate"),
            PromptArgument(name="language", description="Target language"),
        ],
        fn=translate_fn,
    )
    source_manager._prompts["translate"] = translate_prompt

    # Create target manager
    target_manager = PromptManager()

    # Import prompts from source to target
    prefix = "nlp/"
    target_manager.import_prompts(source_manager, prefix)

    # Verify prompts were imported with prefixes
    assert "nlp/summary" in target_manager._prompts
    assert "nlp/translate" in target_manager._prompts

    # Verify the original prompts still exist in source manager
    assert "summary" in source_manager._prompts
    assert "translate" in source_manager._prompts

    # Verify the imported prompts have the correct properties
    assert target_manager._prompts["nlp/summary"].name == "summary"
    assert (
        target_manager._prompts["nlp/summary"].description
        == "Generate a summary of text"
    )

    assert target_manager._prompts["nlp/translate"].name == "translate"
    assert (
        target_manager._prompts["nlp/translate"].description
        == "Translate text to another language"
    )

    # Verify functions were properly copied
    if hasattr(target_manager._prompts["nlp/summary"], "fn"):
        assert target_manager._prompts["nlp/summary"].fn.__name__ == summary_fn.__name__

    if hasattr(target_manager._prompts["nlp/translate"], "fn"):
        assert (
            target_manager._prompts["nlp/translate"].fn.__name__
            == translate_fn.__name__
        )


def test_import_prompts_with_duplicates():
    """Test handling of duplicate prompts during import."""
    # Setup source and target managers with same prompt names
    source_manager = PromptManager()
    target_manager = PromptManager()

    # Add the same prompt name to both managers with functions
    async def source_fn(**kwargs):
        return [{"role": "assistant", "content": "Source content"}]

    async def target_fn(**kwargs):
        return [{"role": "assistant", "content": "Target content"}]

    source_prompt = Prompt(
        name="common",
        description="Source description",
        arguments=None,
        fn=source_fn,
    )
    source_manager._prompts["common"] = source_prompt

    target_prompt = Prompt(
        name="common",
        description="Target description",
        arguments=None,
        fn=target_fn,
    )
    target_manager._prompts["common"] = target_prompt

    # Import prompts with prefix
    prefix = "external/"
    target_manager.import_prompts(source_manager, prefix)

    # Verify both prompts exist in target manager
    assert "common" in target_manager._prompts
    assert "external/common" in target_manager._prompts

    # Verify the functions of both prompts
    if hasattr(target_manager._prompts["common"], "fn") and hasattr(
        target_manager._prompts["external/common"], "fn"
    ):
        assert target_manager._prompts["common"].fn.__name__ == target_fn.__name__
        assert (
            target_manager._prompts["external/common"].fn.__name__ == source_fn.__name__
        )


def test_import_prompts_with_nested_prefixes():
    """Test importing already prefixed prompts."""
    # Setup source manager with already prefixed prompts
    first_manager = PromptManager()
    second_manager = PromptManager()
    third_manager = PromptManager()

    # Add prompt to first manager with a function
    async def analyze_fn(**kwargs):
        return [{"role": "assistant", "content": f"Analysis of: {kwargs.get('text')}"}]

    original_prompt = Prompt(
        name="analyze",
        description="Analyze text",
        arguments=[PromptArgument(name="text", description="Text to analyze")],
        fn=analyze_fn,
    )
    first_manager._prompts["analyze"] = original_prompt

    # Import to second manager with prefix
    second_manager.import_prompts(first_manager, "text/")

    # Import from second to third with another prefix
    third_manager.import_prompts(second_manager, "ai/")

    # Verify the nested prefixing
    assert "text/analyze" in second_manager._prompts
    assert "ai/text/analyze" in third_manager._prompts

    # Verify the properties of the most nested prompt
    assert third_manager._prompts["ai/text/analyze"].name == "analyze"
    assert third_manager._prompts["ai/text/analyze"].description == "Analyze text"

    # Verify function was properly copied through multiple imports
    if hasattr(third_manager._prompts["ai/text/analyze"], "fn"):
        assert (
            third_manager._prompts["ai/text/analyze"].fn.__name__ == analyze_fn.__name__
        )
