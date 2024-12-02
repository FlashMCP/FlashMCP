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


