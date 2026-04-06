import asyncio
import os
import shutil
from collections import deque
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

router = APIRouter()

# --- Sync state -----------------------------------------------------------

_running = False
_subscribers: list[asyncio.Queue] = []
_replay_buffer: deque[str] = deque(maxlen=200)
_file_logger = None  # initialised lazily on first trigger


def _get_file_logger():
    global _file_logger
    if _file_logger is None:
        from garminview.core.config import get_config
        from garminview.core.logging import get_sync_logger
        _file_logger = get_sync_logger(get_config().log_dir)
    return _file_logger


def _broadcast(event: str, data: str) -> None:
    msg = f"event: {event}\ndata: {data}\n\n"
    _replay_buffer.append(msg)
    for q in _subscribers:
        q.put_nowait(msg)
    # Mirror to rotating log file
    _get_file_logger().info("[%s] %s", event, data)


# --- Background sync task -------------------------------------------------

async def _run_sync() -> None:
    global _running
    _running = True
    _replay_buffer.clear()
    started = datetime.now(timezone.utc)
    _broadcast("log", f"{'─' * 60}")
    _broadcast("log", f"Sync started at {started.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    _broadcast("log", f"{'─' * 60}")

    try:
        # Step 1: GarminDB download
        garmindb_cli = shutil.which("garmindb_cli.py")
        if garmindb_cli:
            _broadcast("log", "▶ Starting GarminDB download (--latest)...")
            proc = await asyncio.create_subprocess_exec(
                garmindb_cli,
                "--all", "--download", "--import", "--latest",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, "GARMINDB_LOG_LEVEL": "WARNING"},
            )
            async for raw in proc.stdout:
                line = raw.decode().rstrip()
                if "UnknownEnumValue" in line:
                    continue
                _broadcast("log", line)
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

        def _run():
            with get_session_factory(engine)() as session:
                orch = IngestionOrchestrator(session, cfg.health_data_dir)
                orch.run_incremental()
                _broadcast("log", "▶ Running analysis engine...")
                from garminview.analysis.engine import AnalysisEngine
                AnalysisEngine(session).run_all()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _run)

        elapsed = (datetime.now(timezone.utc) - started).seconds
        _broadcast("log", f"✓ Ingestion + analysis complete")
        _broadcast("done", f"Sync finished in {elapsed}s")

    except Exception as exc:
        _broadcast("error", str(exc))
    finally:
        _running = False
        _broadcast("log", f"{'─' * 60}")


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


@router.get("/logs")
def sync_logs(lines: int = Query(default=200, le=2000)):
    """Return the last N lines from the sync log file."""
    from garminview.core.config import get_config
    from pathlib import Path

    log_path = Path(get_config().log_dir).expanduser() / "sync.log"
    if not log_path.exists():
        return {"lines": []}

    with log_path.open("r", encoding="utf-8") as f:
        all_lines = f.readlines()

    return {"lines": [l.rstrip() for l in all_lines[-lines:]]}


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
