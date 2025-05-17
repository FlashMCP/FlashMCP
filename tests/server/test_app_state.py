import pytest
from FlashMCP.server import FlashMCP
from FlashMCP.server.http import create_sse_app, create_streamable_http_app


def test_http_app_sets_mcp_server_state():
    server = FlashMCP(name="StateTest")
    app = server.http_app()
    assert app.state.FlashMCP_server is server


def test_http_app_sse_sets_mcp_server_state():
    server = FlashMCP(name="StateTest")
    app = server.http_app(transport="sse")
    assert app.state.FlashMCP_server is server


def test_create_streamable_http_app_sets_state():
    server = FlashMCP(name="StateTest")
    app = create_streamable_http_app(server, "/mcp")
    assert app.state.FlashMCP_server is server


def test_create_sse_app_sets_state():
    server = FlashMCP(name="StateTest")
    app = create_sse_app(server, message_path="/message", sse_path="/sse")
    assert app.state.FlashMCP_server is server
