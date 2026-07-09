from datetime import datetime

from app.db.models import Community, RiskLevel
from app.weather.client import max_accumulation, fetch_forecast
from app.engine.models import RiskAssessment


def _classify_risk(pct_of_bank: float) -> RiskLevel:
    if pct_of_bank >= 0.95:
        return RiskLevel.EVACUATE
    if pct_of_bank >= 0.80:
        return RiskLevel.WARNING
    if pct_of_bank >= 0.60:
        return RiskLevel.ADVISORY
    return RiskLevel.NORMAL


def _build_message(community: Community, level: RiskLevel, rise_m: float, mm_6h: float, mm_24h: float) -> str:
    labels = {
        RiskLevel.NORMAL: "No flood risk",
        RiskLevel.ADVISORY: "FLOOD ADVISORY",
        RiskLevel.WARNING: "FLOOD WARNING",
        RiskLevel.EVACUATE: "EVACUATE NOW",
    }
    return (
        f"{labels[level]} for {community.name}. "
        f"Rainfall: {mm_6h:.0f}mm (6h), {mm_24h:.0f}mm (24h). "
        f"Predicted rise: {rise_m:.1f}m (bank: {community.bank_height_m:.1f}m)."
    )


async def assess_community(community: Community) -> RiskAssessment:
    forecast = await fetch_forecast(community.lat, community.lon)

    _, max_6h = max_accumulation(forecast.hourly, 6)
    _, max_24h = max_accumulation(forecast.hourly, 24)

    predicted_rise_m = max_24h * community.rain_to_rise_ratio
    pct = predicted_rise_m / community.bank_height_m if community.bank_height_m > 0 else 0
    level = _classify_risk(pct)

    return RiskAssessment(
        community_id=community.id,
        risk_level=level,
        forecast_mm_6h=max_6h,
        forecast_mm_24h=max_24h,
        predicted_rise_m=predicted_rise_m,
        message=_build_message(community, level, predicted_rise_m, max_6h, max_24h),
        assessed_at=datetime.utcnow(),
    )
