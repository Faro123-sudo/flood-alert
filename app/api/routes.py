from datetime import datetime
import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_session
from app.db.models import Community, Alert, Subscriber, RiskLevel
from app.weather.client import fetch_forecast
from app.auth import require_admin, verify_password

html_router = APIRouter(include_in_schema=False)
api_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ── Auth ──

@html_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@html_router.post("/login")
async def login(request: Request, password: str = Form(...)):
    if verify_password(password):
        request.session["admin"] = True
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid password"})


@html_router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# ── Admin pages ──

@html_router.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, session: AsyncSession = Depends(get_session)):
    require_admin(request)
    result = await session.execute(select(Community))
    communities = result.scalars().all()

    comm_data = []
    for c in communities:
        sub_count = await session.execute(
            select(Subscriber).where(Subscriber.community_id == c.id, Subscriber.active == True)
        )
        subs = len(sub_count.scalars().all())
        alert_count = await session.execute(
            select(Alert).where(Alert.community_id == c.id)
        )
        alerts_n = len(alert_count.scalars().all())
        comm_data.append({"id": c.id, "name": c.name, "lat": c.lat, "lon": c.lon,
                          "bank_height_m": c.bank_height_m, "contact_phones": c.contact_phones,
                          "rain_to_rise_ratio": c.rain_to_rise_ratio, "subscribers": subs,
                          "alerts": alerts_n})

    return templates.TemplateResponse("admin.html", {"request": request, "communities": comm_data})


@html_router.get("/admin/communities/new", response_class=HTMLResponse)
async def new_community_page(request: Request):
    require_admin(request)
    return templates.TemplateResponse("community_form.html", {"request": request, "community": None})


@html_router.post("/admin/communities/new")
async def create_community_admin(
    request: Request,
    name: str = Form(...),
    lat: float = Form(...),
    lon: float = Form(...),
    bank_height_m: float = Form(5.0),
    rain_to_rise_ratio: float = Form(0.02),
    contact_phones: str = Form(""),
    session: AsyncSession = Depends(get_session),
):
    require_admin(request)
    community = Community(
        name=name, lat=lat, lon=lon,
        bank_height_m=bank_height_m,
        rain_to_rise_ratio=rain_to_rise_ratio,
        contact_phones=contact_phones,
    )
    session.add(community)
    await session.commit()
    return RedirectResponse("/admin", status_code=303)


@html_router.get("/admin/communities/{community_id}/edit", response_class=HTMLResponse)
async def edit_community_page(request: Request, community_id: int, session: AsyncSession = Depends(get_session)):
    require_admin(request)
    result = await session.execute(select(Community).where(Community.id == community_id))
    community = result.scalar_one_or_none()
    if not community:
        raise HTTPException(404)
    return templates.TemplateResponse("community_form.html", {"request": request, "community": community})


@html_router.post("/admin/communities/{community_id}/edit")
async def update_community_admin(
    request: Request,
    community_id: int,
    name: str = Form(...),
    lat: float = Form(...),
    lon: float = Form(...),
    bank_height_m: float = Form(5.0),
    rain_to_rise_ratio: float = Form(0.02),
    contact_phones: str = Form(""),
    session: AsyncSession = Depends(get_session),
):
    require_admin(request)
    result = await session.execute(select(Community).where(Community.id == community_id))
    community = result.scalar_one_or_none()
    if not community:
        raise HTTPException(404)
    community.name = name
    community.lat = lat
    community.lon = lon
    community.bank_height_m = bank_height_m
    community.rain_to_rise_ratio = rain_to_rise_ratio
    community.contact_phones = contact_phones
    await session.commit()
    return RedirectResponse("/admin", status_code=303)


@html_router.post("/admin/communities/{community_id}/delete")
async def delete_community_admin(request: Request, community_id: int, session: AsyncSession = Depends(get_session)):
    require_admin(request)
    result = await session.execute(select(Community).where(Community.id == community_id))
    community = result.scalar_one_or_none()
    if not community:
        raise HTTPException(404)
    await session.delete(community)
    await session.commit()
    return RedirectResponse("/admin", status_code=303)


@html_router.get("/admin/communities/{community_id}/subscribers", response_class=HTMLResponse)
async def manage_subscribers(request: Request, community_id: int, session: AsyncSession = Depends(get_session)):
    require_admin(request)
    result = await session.execute(select(Community).where(Community.id == community_id))
    community = result.scalar_one_or_none()
    if not community:
        raise HTTPException(404)
    result = await session.execute(
        select(Subscriber).where(Subscriber.community_id == community_id).order_by(desc(Subscriber.created_at))
    )
    subs = result.scalars().all()
    return templates.TemplateResponse("subscribers.html", {
        "request": request, "community": community, "subscribers": subs
    })


@html_router.post("/admin/subscribers/{subscriber_id}/toggle")
async def toggle_subscriber(request: Request, subscriber_id: int, session: AsyncSession = Depends(get_session)):
    require_admin(request)
    result = await session.execute(select(Subscriber).where(Subscriber.id == subscriber_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404)
    sub.active = not sub.active
    await session.commit()
    return RedirectResponse(f"/admin/communities/{sub.community_id}/subscribers", status_code=303)


# ── Two-way SMS webhook (Twilio) ──

@api_router.post("/sms/inbound")
async def sms_inbound(
    From: str = Form(...),
    Body: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    body = Body.strip().upper()
    phone = From.strip()

    if body == "HELP":
        return PlainTextResponse(
            "FloodAlert commands:\n"
            "FLOOD JOIN [Town] - subscribe to alerts\n"
            "FLOOD LEAVE - unsubscribe from all\n"
            "FLOOD STATUS - check current risk\n"
            "FLOOD HELP - this message"
        )

    if body.startswith("FLOOD JOIN"):
        parts = body.split(" ", 2)
        if len(parts) < 3:
            return PlainTextResponse("Reply with: FLOOD JOIN [Town name]")
        town = parts[2]
        result = await session.execute(select(Community))
        communities = result.scalars().all()
        match = None
        for c in communities:
            if c.name.upper() == town:
                match = c
                break
        if not match:
            names = ", ".join(c.name for c in communities)
            return PlainTextResponse(f"Town not found. Available: {names}")
        existing = await session.execute(
            select(Subscriber).where(Subscriber.phone == phone, Subscriber.community_id == match.id)
        )
        sub = existing.scalar_one_or_none()
        if sub:
            sub.active = True
        else:
            session.add(Subscriber(phone=phone, community_id=match.id))
        await session.commit()
        return PlainTextResponse(f"You're subscribed to {match.name} alerts. Reply FLOOD LEAVE to unsubscribe.")

    if body == "FLOOD LEAVE":
        result = await session.execute(
            select(Subscriber).where(Subscriber.phone == phone, Subscriber.active == True)
        )
        for sub in result.scalars().all():
            sub.active = False
        await session.commit()
        return PlainTextResponse("You've been unsubscribed from all alerts. Reply FLOOD JOIN [Town] to re-subscribe.")

    if body == "FLOOD STATUS":
        result = await session.execute(
            select(Subscriber).where(Subscriber.phone == phone, Subscriber.active == True)
        )
        subs = result.scalars().all()
        if not subs:
            return PlainTextResponse("You're not subscribed to any town. Reply FLOOD JOIN [Town] to start.")
        lines = ["Your subscriptions:"]
        for s in subs:
            r = await session.execute(
                select(Alert).where(Alert.community_id == s.community_id).order_by(desc(Alert.created_at)).limit(1)
            )
            latest = r.scalar_one_or_none()
            level = latest.risk_level.value if latest else "normal"
            lines.append(f"{s.community.name}: {level}")
        return PlainTextResponse("\n".join(lines))

    return PlainTextResponse("Reply FLOOD HELP for commands")


# ── Public pages ──

@html_router.get("/communities", response_class=HTMLResponse)
async def communities_redirect():
    return RedirectResponse("/")


@html_router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Community))
    communities = result.scalars().all()

    result = await session.execute(
        select(Alert).options(selectinload(Alert.community)).order_by(desc(Alert.created_at)).limit(20)
    )
    alerts = result.scalars().all()

    comm_risks = await _all_community_risks(session, communities)

    communities_json = json.dumps([
        {"id": c.id, "name": c.name, "lat": c.lat, "lon": c.lon,
         "bank_height_m": c.bank_height_m, "risk_level": comm_risks[c.id]}
        for c in communities
    ])

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "is_admin": request.session.get("admin", False),
        "communities": [
            {**{k: v for k, v in c.__dict__.items() if not k.startswith("_")}, "risk_level": comm_risks[c.id]}
            for c in communities
        ],
        "communities_json": communities_json,
        "alerts": [
            {"community_name": a.community.name, "risk_level": a.risk_level.value,
             "forecast_mm_24h": a.forecast_mm_24h, "predicted_rise_m": a.predicted_rise_m}
            for a in alerts
        ],
    })


@html_router.get("/communities/{community_id}", response_class=HTMLResponse)
async def community_detail(request: Request, community_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Community).where(Community.id == community_id))
    community = result.scalar_one_or_none()
    if not community:
        raise HTTPException(404, "Community not found")

    result = await session.execute(
        select(Alert).where(Alert.community_id == community_id).order_by(desc(Alert.created_at)).limit(50)
    )
    alerts = result.scalars().all()

    r = await session.execute(
        select(Alert).where(Alert.community_id == community_id).order_by(desc(Alert.created_at)).limit(1)
    )
    latest = r.scalar_one_or_none()
    current_risk = latest.risk_level.value if latest else "normal"

    try:
        forecast = await fetch_forecast(community.lat, community.lon)
        labels = [h.time.strftime("%m/%d %H:00") for h in forecast.hourly[:120]]
        data = [h.precipitation_mm for h in forecast.hourly[:120]]
    except Exception:
        labels = []
        data = []

    return templates.TemplateResponse("community.html", {
        "request": request,
        "is_admin": request.session.get("admin", False),
        "community": community,
        "current_risk": current_risk,
        "alerts": [
            {"risk_level": a.risk_level.value, "forecast_mm_24h": a.forecast_mm_24h,
             "predicted_rise_m": a.predicted_rise_m, "message": a.message,
             "created_at": a.created_at.isoformat()}
            for a in alerts
        ],
        "forecast_labels": json.dumps(labels),
        "forecast_data": json.dumps(data),
    })


# ── JSON API (protected behind auth) ──

@api_router.get("/communities")
async def list_communities(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Community))
    communities = result.scalars().all()
    comm_risks = await _all_community_risks(session, communities)
    return [
        {
            "id": c.id, "name": c.name, "lat": c.lat, "lon": c.lon,
            "bank_height_m": c.bank_height_m, "contact_phones": c.contact_phones,
            "rain_to_rise_ratio": c.rain_to_rise_ratio,
            "risk_level": comm_risks[c.id],
            "subscriber_count": await _subscriber_count(session, c.id),
        }
        for c in communities
    ]


@api_router.post("/communities")
async def create_community(
    request: Request,
    name: str, lat: float, lon: float,
    bank_height_m: float = 5.0,
    rain_to_rise_ratio: float = 0.02,
    contact_phones: str = "",
    session: AsyncSession = Depends(get_session),
):
    require_admin(request)
    community = Community(
        name=name, lat=lat, lon=lon,
        bank_height_m=bank_height_m,
        rain_to_rise_ratio=rain_to_rise_ratio,
        contact_phones=contact_phones,
    )
    session.add(community)
    await session.commit()
    return {"id": community.id, "name": community.name}


@api_router.delete("/communities/{community_id}")
async def delete_community(request: Request, community_id: int, session: AsyncSession = Depends(get_session)):
    require_admin(request)
    result = await session.execute(select(Community).where(Community.id == community_id))
    community = result.scalar_one_or_none()
    if not community:
        raise HTTPException(404)
    await session.delete(community)
    await session.commit()
    return {"ok": True}


@api_router.get("/alerts")
async def list_alerts(
    community_id: int | None = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    q = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if community_id:
        q = q.where(Alert.community_id == community_id)
    result = await session.execute(q)
    alerts = result.scalars().all()
    return [
        {
            "id": a.id, "community_id": a.community_id,
            "risk_level": a.risk_level.value, "message": a.message,
            "forecast_mm_6h": a.forecast_mm_6h, "forecast_mm_24h": a.forecast_mm_24h,
            "predicted_rise_m": a.predicted_rise_m, "delivered_count": a.delivered_count,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]


@api_router.get("/status")
async def status():
    return {"service": "flood-alert", "running": True, "time": datetime.utcnow().isoformat()}


@api_router.get("/search")
async def search_places(q: str = ""):
    if len(q.strip()) < 2:
        return []
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "countrycodes": "ng", "limit": 8},
            headers={"User-Agent": "FloodAlert/1.0"},
        )
        resp.raise_for_status()
        results = resp.json()
    return [
        {
            "name": r.get("display_name", "").split(",")[0],
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "display": r.get("display_name", ""),
        }
        for r in results
    ]


# ── Helpers ──

async def _all_community_risks(session: AsyncSession, communities: list[Community]) -> dict[int, str]:
    risks = {}
    for c in communities:
        r = await session.execute(
            select(Alert).where(Alert.community_id == c.id).order_by(desc(Alert.created_at)).limit(1)
        )
        latest = r.scalar_one_or_none()
        risks[c.id] = latest.risk_level.value if latest else "normal"
    return risks


async def _subscriber_count(session: AsyncSession, community_id: int) -> int:
    r = await session.execute(
        select(Subscriber).where(Subscriber.community_id == community_id, Subscriber.active == True)
    )
    return len(r.scalars().all())
