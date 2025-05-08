from FlashMCP import FlashMCP

mcp = FlashMCP()

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=4200,
        path="/my-custom-path/",
        log_level="debug",
    )
