from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, Boolean, Enum, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum

from app.config import settings


class Base(DeclarativeBase):
    pass


class RiskLevel(str, enum.Enum):
    NORMAL = "normal"
    ADVISORY = "advisory"
    WARNING = "warning"
    EVACUATE = "evacuate"


class Community(Base):
    __tablename__ = "communities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    bank_height_m: Mapped[float] = mapped_column(Float, default=5.0)
    advisory_pct: Mapped[float] = mapped_column(Float, default=0.6)
    warning_pct: Mapped[float] = mapped_column(Float, default=0.8)
    evacuate_pct: Mapped[float] = mapped_column(Float, default=0.95)
    rain_to_rise_ratio: Mapped[float] = mapped_column(Float, default=0.02)
    contact_phones: Mapped[str] = mapped_column(String(500), default="")
    timezone: Mapped[str] = mapped_column(String(50), default="Africa/Lagos")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    alerts: Mapped[list["Alert"]] = relationship(back_populates="community", cascade="all, delete-orphan")
    subscribers: Mapped[list["Subscriber"]] = relationship(back_populates="community", cascade="all, delete-orphan")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"))
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel))
    message: Mapped[str] = mapped_column(String(500))
    forecast_mm_6h: Mapped[float | None] = mapped_column(Float, nullable=True)
    forecast_mm_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_rise_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    community: Mapped["Community"] = relationship(back_populates="alerts")


class Subscriber(Base):
    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20))
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    community: Mapped["Community"] = relationship(back_populates="subscribers")


def init_db():
    engine = create_engine(settings.database_url.replace("+aiosqlite", ""), echo=False)
    Base.metadata.create_all(engine)
    return engine
