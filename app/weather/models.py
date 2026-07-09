from pydantic import BaseModel
from datetime import datetime


class HourlyForecast(BaseModel):
    time: datetime
    precipitation_mm: float


class ForecastResponse(BaseModel):
    lat: float
    lon: float
    hourly: list[HourlyForecast]
