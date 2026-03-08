from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio

router = APIRouter()


@router.get("/stream")
async def sync_stream():
    async def event_generator():
        # Yields SSE events: sync progress, completion, errors
        while True:
            # Check sync_log for running jobs
            await asyncio.sleep(1)
            yield f"data: {{\"status\": \"idle\"}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
