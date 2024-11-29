"""FlashMCP CLI tools."""

import importlib.metadata
import subprocess
import sys
from pathlib import Path

import typer

from .utilities.logging import get_logger

logger = get_logger(__name__)

app = typer.Typer(
    name="FlashMCP",
    help="FlashMCP development tools",
    add_completion=False,
    no_args_is_help=True,  # Show help if no args provided
)


@app.command()
def version() -> None:
    """Show the FlashMCP version."""
    try:
        version = importlib.metadata.version("FlashMCP")
        print(f"FlashMCP version {version}")
    except importlib.metadata.PackageNotFoundError:
        print("FlashMCP version unknown (package not installed)")
        sys.exit(1)


@app.command()
def dev(
    file: Path = typer.Argument(
        ...,
        help="Python file to run",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """Run a FlashMCP server with the MCP Inspector."""
    logger.debug("Starting dev server", extra={"file": str(file)})

    try:
        # Run the MCP Inspector command
        process = subprocess.run(
            ["npx", "@modelcontextprotocol/inspector", "uv", "run", str(file)],
            check=True,
        )
        sys.exit(process.returncode)
    except subprocess.CalledProcessError as e:
        logger.error(
            "Dev server failed",
            extra={
                "file": str(file),
                "error": str(e),
                "returncode": e.returncode,
            },
        )
        sys.exit(e.returncode)
    except FileNotFoundError:
        logger.error(
            "npx not found. Please install Node.js and npm.",
            extra={"file": str(file)},
        )
        sys.exit(1)


if __name__ == "__main__":
    app()
