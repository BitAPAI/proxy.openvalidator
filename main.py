import socket
import logging
import asyncio
from fastapi import FastAPI, Request, HTTPException, Response

app = FastAPI()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

id_counter = 0


async def pipe(src, dst):
    try:
        while True:
            data = await src.read(4096)
            if not data:
                break
            dst.write(data)
            await dst.drain()
    except Exception as e:
        logger.error(e)


@app.route("/{host}:{port}", methods=["CONNECT"])
async def proxy(request: Request, host: str, port: int):
    global id_counter
    id_counter += 1
    current_id = id_counter
    logger.info(f"{current_id} - request for {host}:{port}")

    try:
        reader, writer = await asyncio.open_connection(host, port)
    except Exception as e:
        logger.error(f"{current_id} - dial failed {e}")
        raise HTTPException(status_code=503, detail="Dial failed")

    client_reader, client_writer = await request.legacy_stream()

    tasks = [
        asyncio.create_task(pipe(client_reader, writer)),
        asyncio.create_task(pipe(reader, client_writer)),
    ]

    async def cleanup():
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        writer.close()
        await writer.wait_closed()
        client_writer.close()
        await client_writer.wait_closed()

    request.add_event_handler("shutdown", cleanup)

    return Response(status_code=200)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8888)
