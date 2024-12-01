<!-- omit in toc -->
# FlashMCP 🚀

<div align="center">

<strong>The fast, Pythonic way to build MCP servers.</strong>

[![PyPI - Version](https://img.shields.io/pypi/v/FlashMCP.svg)](https://pypi.org/project/FlashMCP)
[![Tests](https://github.com/jlowin/FlashMCP/actions/workflows/run-tests.yml/badge.svg)](https://github.com/jlowin/FlashMCP/actions/workflows/run-tests.yml)
[![License](https://img.shields.io/github/license/jlowin/FlashMCP.svg)](https://github.com/jlowin/FlashMCP/blob/main/LICENSE)


</div>

[Model Context Protocol (MCP)](https://modelcontextprotocol.io) servers are a new, standardized way to provide context and tools to your LLMs, and FlashMCP makes building MCP servers simple and intuitive. Create tools, expose resources, and define prompts with clean, Pythonic code:

```python
# demo.py

from FlashMCP import FlashMCP


mcp = FlashMCP("Demo 🚀")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b
```

That's it! Give Claude access to the server by running:

```bash
FlashMCP install demo.py
```

FlashMCP handles all the complex protocol details and server management, so you can focus on building great tools. It's designed to be high-level and Pythonic - in most cases, decorating a function is all you need.


### Key features:
* **Fast**: High-level interface means less code and faster development
* **Simple**: Build MCP servers with minimal boilerplate
* **Pythonic**: Feels natural to Python developers
* **Complete***: FlashMCP aims to provide a full implementation of the core MCP specification

(\*emphasis on *aims*)

🚨 🚧 🏗️ *FlashMCP is under active development, as is the MCP specification itself. Core features are working but some advanced capabilities are still in progress.* 


<!-- omit in toc -->
## Table of Contents

- [Installation](#installation)
- [Quickstart](#quickstart)
- [What is MCP?](#what-is-mcp)
- [Core Concepts](#core-concepts)
  - [Server](#server)
  - [Resources](#resources)
  - [Tools](#tools)
  - [Prompts](#prompts)
  - [Images](#images)
  - [Context](#context)
- [Deployment](#deployment)
  - [Development](#development)
    - [Environment Variables](#environment-variables)
  - [Claude Desktop](#claude-desktop)
    - [Environment Variables](#environment-variables-1)
- [Examples](#examples)
  - [Echo Server](#echo-server)
  - [SQLite Explorer](#sqlite-explorer)
- [Contributing](#contributing)

## Installation

```bash
# We strongly recommend installing with uv
brew install uv  # on macOS
uv pip install FlashMCP
```

Or with pip:
```bash
pip install FlashMCP
```

See the [Contributing](#contributing) section for information on how to contribute to FlashMCP.

## Quickstart

Let's create a simple MCP server that exposes a calculator tool and some data:

```python
from FlashMCP import FlashMCP


# Create an MCP server
mcp = FlashMCP("Demo")


# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"
```

To use this server, you have two options:

1. Install it in [Claude Desktop](https://claude.ai/download):
```bash
FlashMCP install server.py
```

2. Test it with the MCP Inspector:
```bash
FlashMCP dev server.py
```

![MCP Inspector](/docs/assets/demo-inspector.png)

## What is MCP?

The [Model Context Protocol (MCP)](https://modelcontextprotocol.io) lets you build servers that expose data and functionality to LLM applications in a secure, standardized way. Think of it like a web API, but specifically designed for LLM interactions. MCP servers can:

- Expose data through **Resources** (think of these sort of like GET endpoints; they are used to load information into the LLM's context)
- Provide functionality through **Tools** (sort of like POST endpoints; they are used to execute code or otherwise produce a side effect)
- Define interaction patterns through **Prompts** (reusable templates for LLM interactions)
- And more!

There is a low-level [Python SDK](https://github.com/modelcontextprotocol/python-sdk) available for implementing the protocol directly, but FlashMCP aims to make that easier by providing a high-level, Pythonic interface.

## Core Concepts


### Server

The FlashMCP server is your core interface to the MCP protocol. It handles connection management, protocol compliance, and message routing:

```python
from FlashMCP import FlashMCP

# Create a named server
mcp = FlashMCP("My App")

# Configure host/port for HTTP transport (optional)
mcp = FlashMCP("My App", host="localhost", port=8000)
```
*Note: All of the following code examples assume you've created a FlashMCP server instance called `mcp`, as shown above.*

### Resources

Resources are how you expose data to LLMs. They're similar to GET endpoints in a REST API - they provide data but shouldn't perform significant computation or have side effects. Some examples:

- File contents
- Database schemas
- API responses
- System information

Resources can be static:
```python
@mcp.resource("config://app")
def get_config() -> str:
    """Static configuration data"""
    return "App configuration here"
```

Or dynamic with parameters (FlashMCP automatically handles these as MCP templates):
```python
@mcp.resource("users://{user_id}/profile")
def get_user_profile(user_id: str) -> str:
    """Dynamic user data"""
    return f"Profile data for user {user_id}"
```

### Tools

Tools let LLMs take actions through your server. Unlike resources, tools are expected to perform computation and have side effects. They're similar to POST endpoints in a REST API.

Simple calculation example:
```python
@mcp.tool()
def calculate_bmi(weight_kg: float, height_m: float) -> float:
    """Calculate BMI given weight in kg and height in meters"""
    return weight_kg / (height_m ** 2)
```

HTTP request example:
```python
import httpx

@mcp.tool()
async def fetch_weather(city: str) -> str:
    """Fetch current weather for a city"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.weather.com/{city}"
        )
        return response.text
```

### Prompts

Prompts are reusable templates that help LLMs interact with your server effectively. They're like "best practices" encoded into your server. A prompt can be as simple as a string:

```python
@mcp.prompt()
def review_code(code: str) -> str:
    return f"Please review this code:\n\n{code}"
```

Or a more structured sequence of messages:
```python
from FlashMCP.prompts.base import UserMessage, AssistantMessage

@mcp.prompt()
def debug_error(error: str) -> list[Message]:
    return [
        UserMessage("I'm seeing this error:"),
        UserMessage(error),
        AssistantMessage("I'll help debug that. What have you tried so far?")
    ]
```


### Images

FlashMCP provides an `Image` class that automatically handles image data in your server:

```python
from FlashMCP import FlashMCP, Image
from PIL import Image as PILImage

@mcp.tool()
def create_thumbnail(image_path: str) -> Image:
    """Create a thumbnail from an image"""
    img = PILImage.open(image_path)
    img.thumbnail((100, 100))
    
    # FlashMCP automatically handles conversion and MIME types
    return Image(data=img.tobytes(), format="png")

@mcp.tool()
def load_image(path: str) -> Image:
    """Load an image from disk"""
    # FlashMCP handles reading and format detection
    return Image(path=path)
```

Images can be used as the result of both tools and resources.

### Context

The Context object gives your tools and resources access to MCP capabilities. To use it, add a parameter annotated with `FlashMCP.Context`:

```python
from FlashMCP import FlashMCP, Context

@mcp.tool()
async def long_task(files: list[str], ctx: Context) -> str:
    """Process multiple files with progress tracking"""
    for i, file in enumerate(files):
        ctx.info(f"Processing {file}")
        await ctx.report_progress(i, len(files))
        
        # Read another resource if needed
        data = await ctx.read_resource(f"file://{file}")
        
    return "Processing complete"
```

The Context object provides:
- Progress reporting through `report_progress()`
- Logging via `debug()`, `info()`, `warning()`, and `error()`
- Resource access through `read_resource()`
- Request metadata via `request_id` and `client_id`

## Deployment

The FlashMCP CLI helps you develop and deploy MCP servers.

Note that for all deployment commands, you are expected to provide the fully qualified path to your server object. For example, if you have a file `server.py` that contains a FlashMCP server named `my_server`, you would provide `path/to/server.py:my_server`.

If your server variable has one of the standard names (`mcp`, `server`, or `app`), you can omit the server name from the path and just provide the file: `path/to/server.py`.

### Development

Test and debug your server with the MCP Inspector:
```bash
# Provide the fully qualified path to your server
FlashMCP dev server.py:my_mcp_server

# Or just the file if your server is named 'mcp', 'server', or 'app'
FlashMCP dev server.py
```

Your server is run in an isolated environment, so you'll need to indicate any dependencies with the `--with` flag. FlashMCP is automatically included. If you are working on a uv project, you can use the `--with-editable` flag to mount your current directory:   

```bash
# With additional packages
FlashMCP dev server.py --with pandas --with numpy

# Using your project's dependencies and up-to-date code
FlashMCP dev server.py --with-editable .
```

#### Environment Variables

The MCP Inspector runs servers in an isolated environment. Environment variables must be set through the Inspector UI and are not inherited from your system. The Inspector does not currently support setting environment variables via command line (see [Issue #94](https://github.com/modelcontextprotocol/inspector/issues/94)).

### Claude Desktop

Install your server in Claude Desktop:
```bash
# Basic usage (name is taken from your FlashMCP instance)
FlashMCP install server.py

# With a custom name
FlashMCP install server.py --name "My Server"

# With dependencies
FlashMCP install server.py --with pandas --with numpy
```

The server name in Claude will be:
1. The `--name` parameter if provided
2. The `name` from your FlashMCP instance
3. The filename if the server can't be imported

#### Environment Variables

Claude Desktop runs servers in an isolated environment. Environment variables from your system are NOT automatically available to the server - you must explicitly provide them during installation:

```bash
# Single env var
FlashMCP install server.py -e API_KEY=abc123

# Multiple env vars
FlashMCP install server.py -e API_KEY=abc123 -e OTHER_VAR=value

# Load from .env file
FlashMCP install server.py -f .env
```

Environment variables persist across reinstalls and are only updated when new values are provided:

```bash
# First install
FlashMCP install server.py -e FOO=bar -e BAZ=123

# Second install - FOO and BAZ are preserved
FlashMCP install server.py -e NEW=value

# Third install - FOO gets new value, others preserved
FlashMCP install server.py -e FOO=newvalue
```

## Examples

Here are a few examples of FlashMCP servers. For more, see the `examples/` directory.

### Echo Server
A simple server demonstrating resources, tools, and prompts:

```python
from FlashMCP import FlashMCP

mcp = FlashMCP("Echo")

@mcp.resource("echo://{message}")
def echo_resource(message: str) -> str:
    """Echo a message as a resource"""
    return f"Resource echo: {message}"

@mcp.tool()
def echo_tool(message: str) -> str:
    """Echo a message as a tool"""
    return f"Tool echo: {message}"

@mcp.prompt()
def echo_prompt(message: str) -> str:
    """Create an echo prompt"""
    return f"Please process this message: {message}"
```

### SQLite Explorer
A more complex example showing database integration:

```python
from FlashMCP import FlashMCP
import sqlite3

mcp = FlashMCP("SQLite Explorer")

@mcp.resource("schema://main")
def get_schema() -> str:
    """Provide the database schema as a resource"""
    conn = sqlite3.connect("database.db")
    schema = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return "\n".join(sql[0] for sql in schema if sql[0])

@mcp.tool()
def query_data(sql: str) -> str:
    """Execute SQL queries safely"""
    conn = sqlite3.connect("database.db")
    try:
        result = conn.execute(sql).fetchall()
        return "\n".join(str(row) for row in result)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.prompt()
def analyze_table(table: str) -> str:
    """Create a prompt template for analyzing tables"""
    return f"""Please analyze this database table:
Table: {table}
Schema: 
{get_schema()}

What insights can you provide about the structure and relationships?"""
```

## Contributing

<details>

<summary><h3>Open Developer Guide</h3></summary>

#### Prerequisites

FlashMCP requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

#### Installation

Create a fork of this repository, then clone it:

```bash
git clone https://github.com/YouFancyUserYou/FlashMCP.git
cd FlashMCP
```

Next, create a virtual environment and install FlashMCP:

```bash
uv venv
source .venv/bin/activate
uv sync --frozen --all-extras --dev
```



#### Testing

Please make sure to test any new functionality. Your tests should be simple and atomic and anticipate change rather than cement complex patterns.

Run tests from the root directory:


```bash
pytest -vv
```

#### Formatting

FlashMCP enforces a variety of required formats, which you can automatically enforce with pre-commit. 

Install the pre-commit hooks:

```bash
pre-commit install
```

The hooks will now run on every commit (as well as on every PR). To run them manually:

```bash
pre-commit run --all-files
```

#### Opening a Pull Request

Fork the repository and create a new branch:

```bash
git checkout -b my-branch
```

Make your changes and commit them:


```bash
git add . && git commit -m "My changes"
```

Push your changes to your fork:


```bash
git push origin my-branch
```

Feel free to reach out in a GitHub issue or discussion if you have any questions!

</details>
