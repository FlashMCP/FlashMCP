from FlashMCP import FlashMCP
from FlashMCP.testing import TestClient

server = FlashMCP("test-server")


@server.tool()
def get_the_value_of_schleeb() -> int:
    return 42


async def main():
    async with TestClient(server) as client:
        await client.say("What is the value of schleeb?")
        await client.say("sorry can you repeat that?")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
