from fastapi import APIRouter, Query, Request

from app.schemas import FighterSearchResponse
from app.services.winner_model import WinnerModelService

router = APIRouter(prefix="/fighters", tags=["fighters"])


def _service(request: Request) -> WinnerModelService:
    return request.app.state.winner_model


@router.get("/search", response_model=FighterSearchResponse)
def search_fighters(
    request: Request,
    q: str = Query(default="", max_length=100),
) -> FighterSearchResponse:
    return FighterSearchResponse(fighters=_service(request).search_fighters(q))
