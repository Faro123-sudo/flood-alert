from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./flood_alerts.db"
    weather_api_base: str = "https://api.open-meteo.com/v1"
    forecast_hours: int = 168
    sms_provider: str = "console"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    check_interval_minutes: int = 30
    alert_cooldown_minutes: int = 30
    admin_password: str = "floodalert2024"
    session_secret: str = "change-this-to-a-random-secret-in-production"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
