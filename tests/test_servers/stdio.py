import asyncio

import FlashMCP_server

if __name__ == "__main__":
    asyncio.run(FlashMCP_server.server.run_stdio_async())
