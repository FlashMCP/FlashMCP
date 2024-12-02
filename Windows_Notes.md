# Getting your development environment set up properly
To get your environment up and running properly, you'll need a slightly different set of commands that are windows specific:
```bash
uv venv
.venv\Scripts\activate
uv pip install -e ".[dev]"
```

This will install the package in editable mode, and install the development dependencies.


# Fixing `AttributeError: module 'collections' has no attribute 'Callable'`
- open `.venv\Lib\site-packages\pyreadline\py3k_compat.py`
- change `return isinstance(x, collections.Callable)` to 
``` 
from collections.abc import Callable
return isinstance(x, Callable)
```

# Helpful notes
For developing FlashMCP
## Install local development version of FlashMCP into a local FlashMCP project server
- ensure
- change directories to your FlashMCP Server location so you can install it in your .venv
- run `.venv\Scripts\activate` to activate your virtual environment
- Then run a series of commands to uninstall the old version and install the new
```bash
# First uninstall
uv pip uninstall FlashMCP

# Clean any build artifacts in your FlashMCP directory
cd C:\path\to\FlashMCP
del /s /q *.egg-info

# Then reinstall in your weather project
cd C:\path\to\new\FlashMCP_server
uv pip install --no-cache-dir -e C:\Users\justj\PycharmProjects\FlashMCP

# Check that it installed properly and has the correct git hash
pip show FlashMCP
```

## Running the FlashMCP server with Inspector
MCP comes with a node.js application called Inspector that can be used to inspect the FlashMCP server. To run the inspector, you'll need to install node.js and npm. Then you can run the following commands:
```bash
FlashMCP dev server.py
```
This will launch a web app on http://localhost:5173/ that you can use to inspect the FlashMCP server.




