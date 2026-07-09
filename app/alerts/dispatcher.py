from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Community, Alert, Subscriber, RiskLevel
from app.engine.risk import assess_community
from app.alerts.sms import get_sms_provider


async def check_and_alert(session: AsyncSession):
    result = await session.execute(select(Community))
    communities = result.scalars().all()
    sms = get_sms_provider()

    for community in communities:
        assessment = await assess_community(community)

        if assessment.risk_level == RiskLevel.NORMAL:
            continue

        recent = await session.execute(
            select(Alert).where(
                Alert.community_id == community.id,
                Alert.risk_level == assessment.risk_level,
                Alert.created_at > datetime.utcnow() - timedelta(hours=1),
            )
        )
        if recent.first():
            continue

        alert = Alert(
            community_id=community.id,
            risk_level=assessment.risk_level,
            message=assessment.message,
            forecast_mm_6h=assessment.forecast_mm_6h,
            forecast_mm_24h=assessment.forecast_mm_24h,
            predicted_rise_m=assessment.predicted_rise_m,
        )
        session.add(alert)
        await session.commit()

        delivered = 0
        phones = [p.strip() for p in community.contact_phones.split(",") if p.strip()]
        for phone in phones:
            try:
                sms.send(phone, assessment.message)
                delivered += 1
            except Exception as e:
                print(f"[SMS FAILED to {phone}]: {e}")

        sub_result = await session.execute(
            select(Subscriber).where(
                Subscriber.community_id == community.id,
                Subscriber.active == True,
            )
        )
        for sub in sub_result.scalars().all():
            try:
                sms.send(sub.phone, assessment.message)
                delivered += 1
            except Exception as e:
                print(f"[SMS FAILED to subscriber {sub.phone}]: {e}")

        alert.delivered_count = delivered
        await session.commit()
