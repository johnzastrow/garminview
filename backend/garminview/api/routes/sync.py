import asyncio
import shutil
from collections import deque
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter()

# --- Sync state -----------------------------------------------------------

_running = False
_subscribers: list[asyncio.Queue] = []
_replay_buffer: deque[str] = deque(maxlen=200)  # last 200 lines for late joiners


def _broadcast(event: str, data: str) -> None:
    msg = f"event: {event}\ndata: {data}\n\n"
    _replay_buffer.append(msg)
    for q in _subscribers:
        q.put_nowait(msg)


# --- Background sync task -------------------------------------------------

async def _run_sync() -> None:
    global _running
    _running = True
    _replay_buffer.clear()
    try:
        # Step 1: GarminDB download
        garmindb_cli = shutil.which("garmindb_cli.py")
        if garmindb_cli:
            _broadcast("log", "▶ Starting GarminDB download (--latest)...")
            # create_subprocess_exec passes args as a list — no shell, no injection risk
            proc = await asyncio.create_subprocess_exec(
                garmindb_cli,
                "--all", "--download", "--import", "--analyze", "--latest",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for raw in proc.stdout:
                _broadcast("log", raw.decode().rstrip())
            rc = await proc.wait()
            if rc != 0:
                _broadcast("error", f"garmindb_cli.py exited with code {rc}")
                return
            _broadcast("log", "✓ GarminDB download complete")
        else:
            _broadcast("log", "⚠ garmindb_cli.py not found on PATH — skipping download step")

        # Step 2: GarminView ingestion
        _broadcast("log", "▶ Starting GarminView ingestion (last 7 days)...")
        from garminview.core.config import get_config
        from garminview.core.database import create_db_engine, get_session_factory
        from garminview.ingestion.orchestrator import IngestionOrchestrator

        cfg = get_config()
        engine = create_db_engine(cfg)
        start = date.today() - timedelta(days=7)
        with get_session_factory(engine)() as session:
            orch = IngestionOrchestrator(session, cfg.health_data_dir)
            orch.run_incremental(start, date.today())

        _broadcast("log", "✓ Ingestion complete")
        _broadcast("done", "Sync finished successfully")

    except Exception as exc:
        _broadcast("error", str(exc))
    finally:
        _running = False


# --- Routes ---------------------------------------------------------------

@router.post("/trigger")
async def trigger_sync():
    global _running
    if _running:
        raise HTTPException(status_code=409, detail="Sync already running")
    asyncio.create_task(_run_sync())
    return {"status": "started"}


@router.get("/status")
def sync_status():
    return {"running": _running}


@router.get("/stream")
async def sync_stream():
    """SSE endpoint — streams log lines to all connected clients."""
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.append(q)

    # Replay recent lines so late-joining clients catch up
    for msg in list(_replay_buffer):
        q.put_nowait(msg)
    if not _running:
        q.put_nowait("event: status\ndata: idle\n\n")

    async def generator():
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=30)
                    yield msg
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: \n\n"  # keep-alive
        finally:
            _subscribers.remove(q)

    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
