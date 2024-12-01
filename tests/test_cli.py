"""Tests for the FlashMCP CLI."""

import json
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from FlashMCP.cli.cli import app, _parse_env_var


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock Claude config file."""
    config = {"mcpServers": {}}
    config_file = tmp_path / "claude_desktop_config.json"
    config_file.write_text(json.dumps(config))
    return config_file


@pytest.fixture
def mock_server_file(tmp_path):
    """Create a mock server file."""
    server_file = tmp_path / "server.py"
    server_file.write_text(
        "from FlashMCP import Server\n" "server = Server(name='test')\n"
    )
    return server_file


@pytest.fixture
def mock_env_file(tmp_path):
    """Create a mock .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\nBAZ=123")
    return env_file


def test_parse_env_var():
    """Test parsing environment variables."""
    assert _parse_env_var("FOO=bar") == ("FOO", "bar")
    assert _parse_env_var("FOO=") == ("FOO", "")
    assert _parse_env_var("FOO=bar baz") == ("FOO", "bar baz")
    assert _parse_env_var("FOO = bar ") == ("FOO", "bar")

    with pytest.raises(SystemExit):
        _parse_env_var("invalid")


@pytest.mark.parametrize(
    "args,expected_env",
    [
        # Basic env var
        (
            ["--env-var", "FOO=bar"],
            {"FOO": "bar"},
        ),
        # Multiple env vars
        (
            ["--env-var", "FOO=bar", "--env-var", "BAZ=123"],
            {"FOO": "bar", "BAZ": "123"},
        ),
        # Env var with spaces
        (
            ["--env-var", "FOO=bar baz"],
            {"FOO": "bar baz"},
        ),
    ],
)
def test_install_with_env_vars(mock_config, mock_server_file, args, expected_env):
    """Test installing with environment variables."""
    runner = CliRunner()

    with (
        patch("FlashMCP.cli.claude.get_claude_config_path") as mock_config_path,
        patch("FlashMCP.cli.cli._import_server") as mock_import,
    ):
        mock_config_path.return_value = mock_config.parent
        mock_server = Mock()
        mock_server.name = "test"  # Set name as an attribute
        mock_import.return_value = mock_server

        result = runner.invoke(
            app,
            ["install", str(mock_server_file)] + args,
        )

        assert result.exit_code == 0

        # Read the config file and check env vars
        config = json.loads(mock_config.read_text())
        assert "mcpServers" in config
        assert len(config["mcpServers"]) == 1
        server = next(iter(config["mcpServers"].values()))
        assert server["env"] == expected_env


def test_install_with_env_file(mock_config, mock_server_file, mock_env_file):
    """Test installing with environment variables from a file."""
    runner = CliRunner()

    with (
        patch("FlashMCP.cli.claude.get_claude_config_path") as mock_config_path,
        patch("FlashMCP.cli.cli._import_server") as mock_import,
    ):
        mock_config_path.return_value = mock_config.parent
        mock_server = Mock()
        mock_server.name = "test"  # Set name as an attribute
        mock_import.return_value = mock_server

        result = runner.invoke(
            app,
            ["install", str(mock_server_file), "--env-file", str(mock_env_file)],
        )

        assert result.exit_code == 0

        # Read the config file and check env vars
        config = json.loads(mock_config.read_text())
        assert "mcpServers" in config
        assert len(config["mcpServers"]) == 1
        server = next(iter(config["mcpServers"].values()))
        assert server["env"] == {"FOO": "bar", "BAZ": "123"}


def test_install_preserves_existing_env_vars(mock_config, mock_server_file):
    """Test that installing preserves existing environment variables."""
    # Set up initial config with env vars
    config = {
        "mcpServers": {
            "test": {
                "command": "uv",
                "args": [
                    "run",
                    "--with",
                    "FlashMCP",
                    "FlashMCP",
                    "run",
                    str(mock_server_file),
                ],
                "env": {"FOO": "bar", "BAZ": "123"},
            }
        }
    }
    mock_config.write_text(json.dumps(config))

    runner = CliRunner()

    with (
        patch("FlashMCP.cli.claude.get_claude_config_path") as mock_config_path,
        patch("FlashMCP.cli.cli._import_server") as mock_import,
    ):
        mock_config_path.return_value = mock_config.parent
        mock_server = Mock()
        mock_server.name = "test"  # Set name as an attribute
        mock_import.return_value = mock_server

        # Install with a new env var
        result = runner.invoke(
            app,
            ["install", str(mock_server_file), "--env-var", "NEW=value"],
        )

        assert result.exit_code == 0

        # Read the config file and check env vars are preserved
        config = json.loads(mock_config.read_text())
        server = next(iter(config["mcpServers"].values()))
        assert server["env"] == {"FOO": "bar", "BAZ": "123", "NEW": "value"}


def test_install_updates_existing_env_vars(mock_config, mock_server_file):
    """Test that installing updates existing environment variables."""
    # Set up initial config with env vars
    config = {
        "mcpServers": {
            "test": {
                "command": "uv",
                "args": [
                    "run",
                    "--with",
                    "FlashMCP",
                    "FlashMCP",
                    "run",
                    str(mock_server_file),
                ],
                "env": {"FOO": "bar", "BAZ": "123"},
            }
        }
    }
    mock_config.write_text(json.dumps(config))

    runner = CliRunner()

    with (
        patch("FlashMCP.cli.claude.get_claude_config_path") as mock_config_path,
        patch("FlashMCP.cli.cli._import_server") as mock_import,
    ):
        mock_config_path.return_value = mock_config.parent
        mock_server = Mock()
        mock_server.name = "test"  # Set name as an attribute
        mock_import.return_value = mock_server

        # Update an existing env var
        result = runner.invoke(
            app,
            ["install", str(mock_server_file), "--env-var", "FOO=newvalue"],
        )

        assert result.exit_code == 0

        # Read the config file and check env var was updated
        config = json.loads(mock_config.read_text())
        server = next(iter(config["mcpServers"].values()))
        assert server["env"] == {"FOO": "newvalue", "BAZ": "123"}
