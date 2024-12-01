"""Claude app integration utilities."""

import json
import sys
from pathlib import Path
from typing import Optional

from ..utilities.logging import get_logger

logger = get_logger(__name__)


def get_claude_config_path() -> Path | None:
    """Get the Claude config directory based on platform."""
    if sys.platform == "win32":
        path = Path(Path.home(), "AppData", "Roaming", "Claude")
    elif sys.platform == "darwin":
        path = Path(Path.home(), "Library", "Application Support", "Claude")
    else:
        return None

    if path.exists():
        return path
    return None


def update_claude_config(
    file_spec: str,
    server_name: str,
    *,
    with_editable: Optional[Path] = None,
    with_packages: Optional[list[str]] = None,
    force: bool = False,
) -> bool:
    """Add the MCP server to Claude's configuration.

    Args:
        file_spec: Path to the server file, optionally with :object suffix
        server_name: Name for the server in Claude's config
        with_editable: Optional directory to install in editable mode
        with_packages: Optional list of additional packages to install
        force: If True, replace existing server with same name
    """
    config_dir = get_claude_config_path()
    if not config_dir:
        return False

    config_file = config_dir / "claude_desktop_config.json"
    if not config_file.exists():
        return False

    try:
        config = json.loads(config_file.read_text())
        if "mcpServers" not in config:
            config["mcpServers"] = {}

        if server_name in config["mcpServers"]:
            if not force:
                logger.warning(
                    f"Server '{server_name}' already exists in Claude config. "
                    "Use `--force` to replace.",
                    extra={"config_file": str(config_file)},
                )
                return False
            logger.info(
                f"Replacing existing server '{server_name}' in Claude config",
                extra={"config_file": str(config_file)},
            )

        # Build uv run command
        args = ["run", "--with", "FlashMCP"]

        if with_editable:
            args.extend(["--with-editable", str(with_editable)])

        if with_packages:
            for pkg in with_packages:
                if pkg:
                    args.extend(["--with", pkg])

        # Convert file path to absolute before adding to command
        # Split off any :object suffix first
        if ":" in file_spec:
            file_path, server_object = file_spec.rsplit(":", 1)
            file_spec = f"{Path(file_path).resolve()}:{server_object}"
        else:
            file_spec = str(Path(file_spec).resolve())

        # Add FlashMCP run command
        args.extend(["FlashMCP", "run", file_spec])

        config["mcpServers"][server_name] = {
            "command": "uv",
            "args": args,
        }

        config_file.write_text(json.dumps(config, indent=2))
        logger.info(
            f"Added server '{server_name}' to Claude config",
            extra={"config_file": str(config_file)},
        )
        return True
    except Exception as e:
        logger.error(
            "Failed to update Claude config",
            extra={
                "error": str(e),
                "config_file": str(config_file),
            },
        )
        return False
