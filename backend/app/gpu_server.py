"""GPU worker server: the "YOUR GPU SERVER" box.

    Website -> Generation API (Render) -> RemoteGpuProvider --HTTPS--> THIS SERVER -> job queue -> GPU -> clip.mp4

Run it on the machine with the NVIDIA GPU:
    cd backend && GPU_SERVER_TOKEN=<long-random-secret> uvicorn app.gpu_server:app --host 0.0.0.0 --port 9000

It accepts clip requests, puts them in a FIFO queue, renders them one at a time with local_video (Wan / LTX-Video)
and serves the finished MP4. Only a bearer token protects it: put it behind a tunnel (Cloudflare Tunnel, Tailscale)
or a reverse proxy with HTTPS before exposing it to the internet.

GPU_SERVER_FAKE=1 renders FFmpeg placeholder clips instead of using the GPU (to test the plumbing anywhere).
"""
import hmac
import logging
import os
import queue
import shutil
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import config

log = logging.getLogger("gpu_server")
TOKEN = os.getenv("GPU_SERVER_TOKEN", "").strip()
FAKE = os.getenv("GPU_SERVER_FAKE", "").strip().lower() in ("1", "true", "yes", "on")
MAX_WAITING = int(os.getenv("GPU_SERVER_MAX_QUEUE", "200") or 200)
KEEP_SECONDS = int(os.getenv("GPU_SERVER_KEEP_SECONDS", "3600") or 3600)
WORK = config.STORAGE / "gpu_server"
WORK.mkdir(parents=True, exist_ok=True)
QUALITY_RES = {"turbo": 480, "balanced": 720, "quality": 1080}

_jobs: Dict[str, dict] = {}
_lock = threading.Lock()
_q: "queue.Queue[str]" = queue.Queue()
_stop = threading.Event()

def _public(j: dict) -> dict:
    with _lock:
        waiting = [k for k, v in _jobs.items() if v["status"] == "queued"]
    pos = waiting.index(j["id"]) + 1 if j["status"] == "queued" and j["id"] in waiting else 0
    return {"id": j["id"], "status": j["status"], "error": j.get("error"), "position": pos,
            "progress": j.get("progress", 0.0), "message": j.get("message", "")}

def _render(j: dict) -> None:
    out = WORK / f"{j['id']}.mp4"
    image = Path(j["image"]) if j.get("image") else None
    if FAKE:
        from .services.video_provider import MockProvider
        config.apply_quality(j["quality"])
        MockProvider()._clip(j["prompt"], j["duration"], j["aspect"], out, image)
        return
    from .services import local_video
    config.apply_quality(j["quality"])
    local_video.set_progress(lambda msg, frac=None: j.update(message=msg, **({"progress": frac} if frac is not None else {})))
    local_video.generate(j["prompt"], j["duration"], j["aspect"], out, image=image)

def _worker() -> None:
    while not _stop.is_set():
        try:
            jid = _q.get(timeout=1)
        except queue.Empty:
            _gc()
            continue
        j = _jobs.get(jid)
        if not j or j["status"] == "cancelled":
            continue
        j["status"] = "running"
        t0 = time.time()
        try:
            _render(j)
            j.update(status="done", progress=1.0, finished=time.time())
            log.info("clip %s done in %.0fs", jid, time.time() - t0)
        except Exception as e:
            log.exception("clip %s failed", jid)
            j.update(status="failed", error=str(e)[:500], finished=time.time())
        finally:
            if j.get("image"):
                Path(j["image"]).unlink(missing_ok=True)

def _gc() -> None:
    now = time.time()
    for jid, j in list(_jobs.items()):
        if j.get("finished") and now - j["finished"] > KEEP_SECONDS:
            (WORK / f"{jid}.mp4").unlink(missing_ok=True)
            _jobs.pop(jid, None)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not TOKEN:
        raise RuntimeError("Set GPU_SERVER_TOKEN to a long random secret before starting the GPU server.")
    t = threading.Thread(target=_worker, daemon=True, name="gpu-worker")
    t.start()
    yield
    _stop.set()

app = FastAPI(title="Reelwright GPU server", lifespan=lifespan)

def auth(authorization: Optional[str] = Header(None)) -> None:
    got = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(got.encode(), TOKEN.encode()):
        raise HTTPException(401, "bad token")

@app.get("/health")
def health(_: None = Depends(auth)):
    info = {"ok": True, "fake": FAKE, "queued": _q.qsize(), "gpu": None}
    if not FAKE:
        try:
            import torch
            if torch.cuda.is_available():
                info["gpu"] = torch.cuda.get_device_name(0)
            else:
                return {**info, "ok": False, "error": "No CUDA GPU visible to PyTorch"}
        except ImportError:
            return {**info, "ok": False, "error": "PyTorch is not installed (pip install -r requirements-gpu.txt)"}
    return info

@app.post("/clip", status_code=202)
async def submit(prompt: str = Form(...), duration: int = Form(5), aspect: str = Form("16:9"),
                 quality: str = Form("balanced"), image: Optional[UploadFile] = File(None), _: None = Depends(auth)):
    if _q.qsize() >= MAX_WAITING:
        raise HTTPException(429, "GPU queue is full")
    if quality not in QUALITY_RES:
        quality = "balanced"
    jid = uuid.uuid4().hex
    img_path = None
    if image is not None:
        img_path = WORK / f"{jid}{Path(image.filename or 'x.png').suffix.lower() or '.png'}"
        with img_path.open("wb") as f:
            shutil.copyfileobj(image.file, f)
    j = dict(id=jid, status="queued", prompt=prompt[:2000], duration=max(1, min(30, duration)), aspect=aspect,
             quality=quality, image=str(img_path) if img_path else None, created=time.time())
    _jobs[jid] = j
    _q.put(jid)
    return _public(j)

def _get(jid: str) -> dict:
    j = _jobs.get(jid)
    if not j:
        raise HTTPException(404, "unknown clip")
    return j

@app.get("/clip/{jid}")
def status(jid: str, _: None = Depends(auth)):
    return _public(_get(jid))

@app.get("/clip/{jid}/video")
def video(jid: str, _: None = Depends(auth)):
    j = _get(jid)
    f = WORK / f"{jid}.mp4"
    if j["status"] != "done" or not f.exists():
        raise HTTPException(409, "clip is not ready")
    return FileResponse(f, media_type="video/mp4")

@app.delete("/clip/{jid}")
def cancel(jid: str, _: None = Depends(auth)):
    j = _get(jid)
    if j["status"] == "queued":
        j["status"] = "cancelled"
    return {"ok": True}
