from pydantic import BaseModel
from datetime import datetime

from app.db.models import RiskLevel


class RiskAssessment(BaseModel):
    community_id: int
    risk_level: RiskLevel
    forecast_mm_6h: float
    forecast_mm_24h: float
    predicted_rise_m: float
    message: str
    assessed_at: datetime
