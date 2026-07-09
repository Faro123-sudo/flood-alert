from datetime import datetime, timezone

import httpx

from app.config import settings
from app.weather.models import ForecastResponse, HourlyForecast


async def fetch_forecast(lat: float, lon: float) -> ForecastResponse:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation",
        "timezone": "auto",
        "forecast_days": "7",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{settings.weather_api_base}/forecast", params=params)
        resp.raise_for_status()
        data = resp.json()

    hourly = []
    for t_str, prec in zip(data["hourly"]["time"], data["hourly"]["precipitation"]):
        hourly.append(
            HourlyForecast(
                time=datetime.fromisoformat(t_str).replace(tzinfo=None),
                precipitation_mm=prec if prec is not None else 0.0,
            )
        )
    return ForecastResponse(lat=lat, lon=lon, hourly=hourly)


def accumulate_precipitation(
    hourly: list[HourlyForecast], window_hours: int
) -> list[tuple[datetime, float]]:
    result = []
    for i in range(len(hourly)):
        window_start = i - window_hours + 1
        if window_start < 0:
            continue
        total = sum(h.precipitation_mm for h in hourly[window_start : i + 1])
        result.append((hourly[i].time, total))
    return result


def max_accumulation(
    hourly: list[HourlyForecast], window_hours: int
) -> tuple[datetime, float]:
    acc = accumulate_precipitation(hourly, window_hours)
    if not acc:
        return datetime.utcnow(), 0.0
    return max(acc, key=lambda x: x[1])
