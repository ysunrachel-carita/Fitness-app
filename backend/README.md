# Backend Service

The core Python/Flask application that handles data persistence, user authentication, and business logic for the Fitness App.

## 🧱 Architecture Principles

1.  **Postgres-Only**: We have sunsetted all SQLite support. The app connects exclusively to PostgreSQL.
2.  **Explicit Migrations**: Schema changes are managed via versioned SQL files in `migrations/`. No "auto-migrating" code exists in the application startup.
3.  **PgWrapper**: Since the codebase was originally written for SQLite, we use a custom `PgWrapper` class in `app.py` to translate standard SQL patterns and handle connection pooling.

## ⚙️ Environment Variables

Create a `backend/.env` file with the following keys:

```bash
# Flask
SECRET_KEY=your_secret_here

# Database (Local Docker)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fitness_app

# Database (Production/Remote)
RENDER_DATABASE_URL=postgresql://postgres.xxx:password@aws-xxxx.supabase.com:6543/postgres
```

## 🏗 Key Components

### `app.py`
The main entry point. It contains:
*   Route definitions for all pages and APIs.
*   `PgWrapper`: The database interface layer.
*   Authentication logic (session-based).

### `scripts/migrate.py`
The CLI tool for database maintenance. 
*   Use `--target local` for development.
*   Use `--target remote` for production (includes automatic `pg_dump` backups).

### `migrations/`
Contains the cumulative history of the database schema. `001_baseline_schema.sql` represents the consolidated state as of April 2026.

## 🧪 Development Workflow

1.  **Logic Changes**: Modify `app.py` or templates.
2.  **Schema Changes**: 
    *   Run `python scripts/migrate.py new "description"`
    *   Edit the SQL file.
    *   Apply locally with `python scripts/migrate.py --target local`.
3.  **Static Assets**: Update files in `static/` (CSS/JS).
