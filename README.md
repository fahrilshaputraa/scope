# Project Control Center (PCC)

Internal project management & progress monitoring system — a centralized
**Project Control Center** for Project Managers, Project Leads, and Management.

Bukan sekadar task management: PCC memberikan visibility terhadap progress
project, planned vs actual, timeline (Gantt/Waterfall), milestone, issues,
notes, dan reporting management — semua dari satu aplikasi.

## Stack

- **Django** + **HTMX** (server-rendered, tanpa build step frontend)
- **Chart.js** — Plan vs Actual progress chart
- **Frappe Gantt** — Waterfall / Gantt timeline
- **Authlib** — Microsoft Entra ID SSO
- **PostgreSQL** di produksi, **SQLite** untuk development lokal
- **Whitenoise** — static file serving

## Development

```bash
uv sync
uv run manage.py migrate
uv run manage.py seed_demo        # data demo (optional)
uv run manage.py runserver
```

Testing:

```bash
uv run pytest
uv run ruff check .
```

## Environment

Lihat `.env.example`.

Variabel utama:

| Var | Keterangan |
|---|---|
| `DJANGO_SECRET_KEY` | Secret key Django |
| `DJANGO_DEBUG` | `true` untuk development |
| `DATABASE_URL` | `postgres://user:pass@host:5432/db` (kosong = SQLite) |
| `AZURE_TENANT_ID` | Entra ID tenant (atau `common`) |
| `AZURE_CLIENT_ID` | Client id app registration |
| `AZURE_CLIENT_SECRET` | Client secret app registration |

Tanpa konfigurasi Entra ID (local dev), login dev tersedia di `/auth/dev/`.

## Struktur

```
config/          # settings, urls, wsgi/asgi
apps/
  identity/      # auth (Entra ID SSO), roles
  projects/      # project, phase, milestone, progress, notes, decisions, activity
  work/          # task, issue, comments
templates/       # global templates (base layout)
static/          # css, js, vendor libs
tests/           # pytest
```
