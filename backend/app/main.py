import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from .api.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("main")

app = FastAPI(title="Reelwright AI")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)

_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():  # production: one port serves API + UI
    app.mount("/", StaticFiles(directory=_dist, html=True), name="ui")
else:
    log.warning("frontend/dist not found: only the API is served (run `npm run build` in frontend/)")
log.info("providers=%s hf_spaces=%d storage=%s", config.VIDEO_PROVIDERS, len(config.HF_SPACES), config.STORAGE)
