from fastapi import APIRouter, HTTPException, Request, status

from app.schemas import PredictionRequest, PredictionResponse
from app.services.winner_model import WinnerModelService

router = APIRouter(prefix="/predictions", tags=["predictions"])


def _service(request: Request) -> WinnerModelService:
    return request.app.state.winner_model


@router.post("/winner", response_model=PredictionResponse)
def predict_winner(
    payload: PredictionRequest, request: Request
) -> PredictionResponse:
    service: WinnerModelService = _service(request)
    try:
        result = service.predict(
            payload.fighter_a,
            payload.fighter_b,
            title_bout=payload.title_bout,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return PredictionResponse(**result)
