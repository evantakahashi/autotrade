import os
import sys
import signal
import subprocess
from fastapi import APIRouter
from pydantic import BaseModel
from src.api.deps import get_db

router = APIRouter(prefix="/api/loop", tags=["loop"])

# Track the subprocess
_loop_process: subprocess.Popen | None = None


class LoopStartRequest(BaseModel):
    tickers: list[str]
    days: int = 730
    cooldown: int = 3600
    max_rejections: int = 10


@router.get("/status")
def get_loop_status():
    global _loop_process
    db = get_db()
    state = db.get_loop_state()

    process_alive = False
    if _loop_process is not None:
        process_alive = _loop_process.poll() is None

    if state is None:
        return {
            "status": "stopped",
            "paper_trading_experiment": None,
            "paper_start_date": None,
            "consecutive_rejections": 0,
            "process_alive": process_alive,
        }

    return {
        "status": state.get("status", "unknown"),
        "paper_trading_experiment": state.get("paper_trading_experiment"),
        "paper_start_date": str(state.get("paper_start_date", "")),
        "consecutive_rejections": state.get("consecutive_rejections", 0),
        "process_alive": process_alive,
    }


@router.post("/start")
def start_loop(req: LoopStartRequest):
    global _loop_process

    # Don't start if already running
    if _loop_process is not None and _loop_process.poll() is None:
        return {"status": "already running", "pid": _loop_process.pid}

    tickers = [t.upper() for t in req.tickers]
    cmd = [
        sys.executable, "research.py",
        *tickers,
        "--days", str(req.days),
        "--cooldown", str(req.cooldown),
        "--max-rejections", str(req.max_rejections),
    ]

    _loop_process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return {"status": "started", "pid": _loop_process.pid}


@router.post("/stop")
def stop_loop():
    global _loop_process

    if _loop_process is None or _loop_process.poll() is not None:
        return {"status": "no process running"}

    pid = _loop_process.pid
    os.kill(pid, signal.SIGINT)
    return {"status": "stopping", "pid": pid}
