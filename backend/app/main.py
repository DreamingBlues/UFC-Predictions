from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.fighters import router as fighters_router
from app.routes.predictions import router as predictions_router
from app.services.winner_model import WinnerModelService

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "winner" / "models" / "xgb_min_final.joblib"
DATA_PATH = PROJECT_ROOT / "data_clean" / "w_pre_fight_stats.csv"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # These are deliberately loaded once per application process.
    app.state.winner_model = WinnerModelService(MODEL_PATH, DATA_PATH)
    yield


app = FastAPI(
    title="UFC Winner Prediction API",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(fighters_router)
app.include_router(predictions_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
