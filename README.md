# FlashMCP

> **Note**: This is experimental software. The Model Context Protocol itself is only a few days old and the specification is still evolving.

A fast, pythonic way to build Model Context Protocol (MCP) servers.

Anthropic's new [Model Context Protocol](https://modelcontextprotocol.io) is a powerful way to give broadcast new functionality and context to LLMs. However, developing MCP servers can be cumbersome. FlashMCP provides a simple, intuitive interface for creating MCP servers in Python.

## Table of Contents

- [FlashMCP](#FlashMCP)
  - [Table of Contents](#table-of-contents)
  - [Installation](#installation)
  - [Quick Start](#quick-start)
  - [Core Concepts](#core-concepts)
    - [Resources](#resources)
    - [Tools](#tools)
  - [Development](#development)
    - [Running the Dev Inspector](#running-the-dev-inspector)
    - [Installing in Claude](#installing-in-claude)
  - [License](#license)

## Installation

MCP servers require you to use [uv](https://github.com/astral-sh/uv) as your dependency manager.

Install uv with brew:
```bash
brew install uv
```
*(Editor's note: I was unable to get MCP servers working unless uv was installed with brew.)*

Install FlashMCP:
```bash
uv pip install FlashMCP
```

## Quick Start

Here's a simple example that exposes your desktop directory as a resource and provides a basic addition tool:

```python
from pathlib import Path
from FlashMCP import FlashMCP

# Create server
mcp = FlashMCP("Demo")

@mcp.resource("dir://desktop")
def desktop() -> list[str]:
    """List the files in the user's desktop"""
    desktop = Path.home() / "Desktop"
    return [str(f) for f in desktop.iterdir()]

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

if __name__ == "__main__":
    mcp.run()
```

## Core Concepts

FlashMCP makes it easy to expose two types of functionality to LLMs: Resources and Tools.

### Resources

Resources are data sources that can be accessed by the LLM. They're perfect for providing context like files, API responses, or database queries.

FlashMCP provides a simple `@resource` decorator that handles both static and dynamic resources. While the MCP spec distinguishes between resources and templates, FlashMCP automatically handles this distinction based on your function signature:

```python
# Static resource
@mcp.resource("resource://static")
def get_static() -> str:
    """Return static content"""
    return "Static content"

# Dynamic resource
@mcp.resource("resource://{city}/weather")
def get_weather(city: str) -> str:
    """Get weather for a city"""
    return f"Weather for {city}"

# Multiple parameters are supported
@mcp.resource("db://users/{user_id}/posts/{post_id}")
def get_user_post(user_id: int, post_id: int) -> dict:
    """Get a specific post by a user"""
    return {
        "user_id": user_id,
        "post_id": post_id,
        "content": "Post content..."
    }

# File resources
@mcp.resource("file://config.json") 
def get_config() -> str:
    """Read the config file"""
    return Path("config.json").read_text()
```

Resources can return:
- Strings for text content 
- Bytes for binary content
- Other types will be converted to JSON

When your resource URI includes parameters in curly braces (like `{city}`) and your function accepts matching arguments, FlashMCP automatically sets up a template resource behind the scenes. This means you don't need to worry about the distinction between resources and templates in the MCP spec - just write your function, and FlashMCP handles the rest.

> **Note**: If you're familiar with the MCP spec, you might notice that dynamic resources are implemented as templates under the hood. FlashMCP simplifies this by providing a unified interface through the `@resource` decorator. This is similar to how web frameworks often unify GET and POST handlers under a single route decorator.


### Tools

Tools are functions that can be called by the LLM to perform actions. They're great for calculations, API calls, or any interactive functionality. Tools are defined using the `@tool` decorator:

```python
@mcp.tool()
def search_docs(query: str, max_results: int = 5) -> list[dict]:
    """Search documentation for relevant entries"""
    results = perform_search(query, limit=max_results)
    return [{"title": r.title, "excerpt": r.excerpt} for r in results]

@mcp.tool()
def analyze_image(image_path: str) -> dict:
    """Analyze an image and return metadata"""
    from PIL import Image
    img = Image.open(image_path)
    return {
        "size": img.size,
        "mode": img.mode,
        "format": img.format
    }
```

Tools support:
- Type hints for parameters
- Default values
- Async functions
- Return value conversion to JSON

## Development

FlashMCP includes developer tools to make testing and debugging easier.

### Running the Dev Inspector

The MCP Inspector helps you test your server during development:

```bash
# Basic usage
FlashMCP dev your_server.py

# Install package in editable mode from current directory
FlashMCP dev your_server.py --with-editable .

# Install additional packages
FlashMCP dev your_server.py --with pandas --with numpy

# Combine both
FlashMCP dev your_server.py --with-editable . --with pandas --with numpy
```

The `--with` flag automatically includes `FlashMCP` and any additional packages you specify. The `--with-editable` flag installs the package from the specified directory in editable mode, which is useful during development.

### Installing in Claude

To use your server with Claude Desktop:

```bash
# Basic usage
FlashMCP install your_server.py --name "My Server"

# Install package in editable mode
FlashMCP install your_server.py --with-editable .

# Install additional packages
FlashMCP install your_server.py --with pandas --with numpy

# Combine options
FlashMCP install your_server.py --with-editable . --with pandas --with numpy
```

## License

Apache 2.0