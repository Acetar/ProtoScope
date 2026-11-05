"""
渲染任务：调用 Remotion CLI 出 MP4。

为什么放独立函数 + 线程：渲染 20~60s，不能占住事件循环；
这里用最简单的线程池实现，生产环境换成 arq/Celery（设计文档 7.8）。
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RENDERER = ROOT / "renderer"
WORK = RENDERER / ".work"
OUT = RENDERER / "out"
TMP = RENDERER / ".tmp"
COMPOSITION_ID = "ProtocolFlow"

_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create(props: dict) -> dict:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "status": "queued",
        "url": None,
        "error": None,
        "startedAt": None,
        "finishedAt": None,
    }
    with _lock:
        _jobs[job_id] = job

    thread = threading.Thread(target=_run, args=(job_id, props), daemon=True)
    thread.start()
    return job


def get(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def _update(job_id: str, **fields: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)


def _run(job_id: str, props: dict) -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)

    props_file = WORK / f"{job_id}.json"
    out_file = OUT / f"{job_id}.mp4"
    props_file.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")

    _update(job_id, status="running", startedAt=_now())

    # Windows 上 remotion/ffmpeg 会把中间文件写进系统 TEMP，指到本地避免 Permission denied
    env = {**os.environ, "TEMP": str(TMP), "TMP": str(TMP)}

    cmd = (
        f'npx remotion render src/index.ts {COMPOSITION_ID} "out/{job_id}.mp4" '
        f'--props=".work/{job_id}.json" --concurrency=2'
    )

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(RENDERER),
            env=env,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        _update(job_id, status="failed", error="渲染超时（300s）", finishedAt=_now())
        return

    if proc.returncode != 0 or not out_file.exists():
        tail = (proc.stderr or proc.stdout or "")[-1500:]
        _update(job_id, status="failed", error=tail, finishedAt=_now())
        return

    _update(job_id, status="done", url=f"/media/{job_id}.mp4", finishedAt=_now())
