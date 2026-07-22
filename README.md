# Flood Alert

Real-time flood monitoring and SMS alert system for riverine communities. Uses Open-Meteo weather forecasts to predict river-level rise and dispatches alerts via Twilio SMS (or console fallback).

## Features

- **Automated risk assessment** — Scheduled checks every 30 minutes against Open-Meteo forecasts
- **Four risk levels** — Normal, Advisory, Warning, Evacuate
- **SMS alerts** — Sends alerts to community contacts and subscribers via Twilio (or console for dev)
- **Two-way SMS** — Subscribers can text commands (`FLOOD JOIN`, `FLOOD LEAVE`, `FLOOD STATUS`, `FLOOD HELP`)
- **Admin panel** — Manage communities, contacts, and subscribers (password-protected)
- **Public dashboard** — View community status and forecast charts at `/`
- **JSON API** — REST endpoints for communities and alerts at `/api/`

## Tech Stack

- Python 3.12, FastAPI, SQLAlchemy (async), APScheduler, Jinja2
- SQLite + aiosqlite (default), Twilio (optional)
- Docker + Docker Compose support

## Quick Start

### Local Development

```bash
# Create a virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Seed sample communities
python seed.py

# Run the server
python run.py
```

### Docker

```bash
# Copy and edit environment variables
cp .env.example .env   # or create .env manually

# Start with Docker Compose
docker compose up --build
```

The app runs at **http://localhost:8000**.

## Environment Variables

Create a `.env` file in the project root:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./flood_alerts.db` | Database connection string |
| `SMS_PROVIDER` | `console` | `console` (logs to terminal) or `twilio` |
| `TWILIO_ACCOUNT_SID` | | Twilio account SID (if using Twilio) |
| `TWILIO_AUTH_TOKEN` | | Twilio auth token |
| `TWILIO_FROM_NUMBER` | | Twilio phone number |
| `CHECK_INTERVAL_MINUTES` | `30` | How often forecasts are checked |
| `ALERT_COOLDOWN_MINUTES` | `30` | Minimum time between duplicate alerts |
| `ADMIN_PASSWORD` | `floodalert2024` | Admin panel login password |
| `SESSION_SECRET` | | Session encryption key (change in production) |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Public dashboard |
| `GET` | `/communities/:id` | Community detail page with forecast chart |
| `GET` | `/admin` | Admin panel (login required) |
| `GET` | `/api/communities` | List communities with risk levels (JSON) |
| `GET` | `/api/alerts` | List recent alerts (JSON) |
| `GET` | `/api/status` | Service health check |
| `POST` | `/api/sms/inbound` | Twilio two-way SMS webhook |

## Project Structure

```
flood-alert/
├── app/
│   ├── alerts/          # Alert dispatcher and SMS providers
│   ├── api/             # Routes (HTML + JSON)
│   ├── db/              # SQLAlchemy models and session management
│   ├── engine/          # Risk assessment logic
│   ├── weather/         # Open-Meteo forecast client
│   └── templates/       # Jinja2 HTML templates
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── run.py               # Development server
└── seed.py              # Sample community data
```

## How Risk Is Calculated

1. Fetch 7-day hourly precipitation forecast from Open-Meteo for each community
2. Compute max accumulated rainfall over 6h and 24h windows
3. Predict river rise using the community's `rain_to_rise_ratio`
4. Compare predicted rise to `bank_height_m` to classify risk:

| Risk Level | Threshold |
|---|---|
| Normal | < 60% of bank height |
| Advisory | ≥ 60% of bank height |
| Warning | ≥ 80% of bank height |
| Evacuate | ≥ 95% of bank height |

## License

MIT
