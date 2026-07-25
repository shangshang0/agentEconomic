"""Credential-free loopback publishing proxy.

Docker 29 does not activate host port publishing for a container whose every
network is internal. This tiny proxy is the sole member of both the internal
control network and an ordinary bridge. It owns no experiment/provider secret
and the host port remains bound to 127.0.0.1.
"""

from __future__ import annotations

import asyncio


async def relay(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except ConnectionError:
            pass


async def handle(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    try:
        upstream_reader, upstream_writer = await asyncio.open_connection("backend", 8000)
    except OSError:
        client_writer.close()
        await client_writer.wait_closed()
        return
    await asyncio.gather(relay(client_reader, upstream_writer), relay(upstream_reader, client_writer))


async def main() -> None:
    server = await asyncio.start_server(handle, "0.0.0.0", 8002)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
