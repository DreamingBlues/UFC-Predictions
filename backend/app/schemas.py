from pydantic import BaseModel, Field, field_validator


class PredictionRequest(BaseModel):
    fighter_a: str = Field(min_length=1)
    fighter_b: str = Field(min_length=1)
    title_bout: bool = False

    @field_validator("fighter_a", "fighter_b")
    @classmethod
    def strip_fighter_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("fighter name cannot be empty")
        return value


class PredictionResponse(BaseModel):
    fighter_a: str
    fighter_b: str
    predicted_winner: str
    fighter_a_probability: float = Field(ge=0, le=1)
    fighter_b_probability: float = Field(ge=0, le=1)


class FighterSearchResponse(BaseModel):
    fighters: list[str]
