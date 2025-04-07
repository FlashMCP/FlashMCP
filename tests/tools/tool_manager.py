from FlashMCP.tools.tool_manager import ToolManager


def test_import_tools():
    """Test importing tools from one manager to another with a prefix."""
    # Setup source manager with tools
    source_manager = ToolManager()

    # Create some test tools
    def tool1_fn():
        return "Tool 1 result"

    def tool2_fn():
        return "Tool 2 result"

    # Add tools to source manager
    source_manager.add_tool(tool1_fn, name="get_data", description="Get some data")
    source_manager.add_tool(
        tool2_fn, name="process_data", description="Process the data"
    )

    # Create target manager
    target_manager = ToolManager()

    # Import tools from source to target
    prefix = "source"
    target_manager.import_tools(source_manager, prefix)

    # Verify tools were imported with prefixes
    assert "source:get_data" in target_manager._tools
    assert "source:process_data" in target_manager._tools

    # Verify the original tools still exist in source manager
    assert "get_data" in source_manager._tools
    assert "process_data" in source_manager._tools

    # Verify the imported tools have the correct descriptions
    assert target_manager._tools["source:get_data"].description == "Get some data"
    assert (
        target_manager._tools["source:process_data"].description == "Process the data"
    )

    # Verify the tool functions were properly copied
    # We can't directly compare functions, so we'll check their __name__ attribute
    assert target_manager._tools["source:get_data"].fn.__name__ == tool1_fn.__name__
    assert target_manager._tools["source:process_data"].fn.__name__ == tool2_fn.__name__


def test_import_tools_duplicate_warning(caplog):
    """Test that warning is logged when importing a tool with a name that already exists."""
    # Setup source and target managers
    source_manager = ToolManager()
    target_manager = ToolManager(warn_on_duplicate_tools=True)

    # Add the same tool name to both managers
    def source_fn():
        return "Source result"

    def target_fn():
        return "Target result"

    source_manager.add_tool(source_fn, name="common_tool")
    target_manager.add_tool(
        target_fn, name="source:common_tool"
    )  # Pre-create with the prefixed name

    # Import tools from source to target
    target_manager.import_tools(source_manager, "source")

    # Verify a warning was logged
    assert any("already exists" in record.message for record in caplog.records)

    # The original tool in the target manager should be preserved
    assert target_manager._tools["source:common_tool"].fn.__name__ == target_fn.__name__


def test_import_tools_with_multiple_prefixes():
    """Test importing tools from multiple managers with different prefixes."""
    # Setup source managers
    weather_manager = ToolManager()
    news_manager = ToolManager()

    # Add tools to source managers
    def forecast_fn():
        return "Weather forecast"

    def headlines_fn():
        return "News headlines"

    weather_manager.add_tool(forecast_fn, name="forecast")
    news_manager.add_tool(headlines_fn, name="headlines")

    # Create target manager and import from both sources
    main_manager = ToolManager()
    main_manager.import_tools(weather_manager, "weather")
    main_manager.import_tools(news_manager, "news")

    # Verify tools were imported with correct prefixes
    assert "weather:forecast" in main_manager._tools
    assert "news:headlines" in main_manager._tools

    # Verify the tools are accessible and functioning
    assert main_manager._tools["weather:forecast"].fn.__name__ == forecast_fn.__name__
    assert main_manager._tools["news:headlines"].fn.__name__ == headlines_fn.__name__
