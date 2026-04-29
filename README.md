# Fitness App 🏋️‍♂️

A modern fitness tracking application for logging lifts, WODs, and runs. This project has been modernized to use a single-source-of-truth Postgres architecture with professional migration management.

## 🚀 Quick Start (Local Development)

The easiest way to run the app locally is using Docker. This will spin up both the Flask application and a Postgres database.

```bash
# 1. Start the stack
docker-compose up -d --build

# 2. Apply migrations to the local database
python3 backend/scripts/migrate.py --target local

# 3. Access the app
# Open http://localhost:5000
```

## 🛠 Tech Stack

*   **Backend**: Flask (Python 3.x)
*   **Database**: PostgreSQL (Local: Docker | Production: Supabase)
*   **Infrastructure**: Docker & Docker Compose
*   **Frontend**: HTML5, Vanilla JS, CSS3

## 📁 Project Structure

```text
.
├── backend/            # Flask application code
│   ├── migrations/     # Versioned SQL schema changes
│   ├── scripts/        # Database management utilities (migrate.py)
│   ├── static/         # CSS, Images, and Frontend JS
│   └── templates/      # Jinja2 HTML templates
├── Dockerfile          # Web app container definition
└── docker-compose.yml  # Local stack orchestration (App + DB)
```

## 🏗 Database Management

We use a professional, versioned migration system. **Never** manually edit the schema via a GUI or `psql` shell. Instead, use the migration runner.

See [backend/migrations/README.md](backend/migrations/README.md) for the full migration workflow (scaffolding, testing, and pushing to production).

## 🌍 Production Deployment

The application is configured to deploy to **Render** (Web Service) and **Supabase** (Postgres DB).

1.  Set `DATABASE_URL` to your production Postgres string in the Render environment variables.
2.  Use `python3 scripts/migrate.py --target remote` to push schema changes to production.
