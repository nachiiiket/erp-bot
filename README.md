# ERP AI Analytics

AI-powered sales intelligence chatbot for Best Marine Private Limited. Analyzes ERP sales data (Sales Orders, Invoices) and answers business queries using an LLM agent with tool-calling.

**Live demo:** [https://erp-2w694uaqf-erp-bot-demo.vercel.app/](https://erp-2w694uaqf-erp-bot-demo.vercel.app/)

## Stack

- **Frontend** – Vanilla HTML/CSS/JS (single-page chat UI)
- **Backend** – Django + Django REST Framework
- **LLM** – NVIDIA Nemotron via OpenAI-compatible client library
- **Deployment** – Vercel (Python serverless functions)

## Quick Start

### 1. Clone & install

```bash
cd erp-bot
pip install -r requirements.txt
```

### 2. Configure `.env`

Copy `.env.example` to `.env` inside `llm_project/` and fill in:

```ini
NVIDIA_API_KEY=nvapi-...     # from NVIDIA API console
DJANGO_SECRET_KEY=your-secret-key
```

### 3. Run locally

```bash
cd llm_project
python manage.py runserver
```

Open `http://localhost:8000` – the Django view serves the frontend. Enter your auth token in the popup to start querying.

## Auth Token

The frontend pops up asking for an **access token**.

> **Trial access:** Use `nv-token-2603` to try the app. No separate API key needed on your side.

## API Endpoints

All endpoints require `Authorization: Bearer <token>` header.

| Method | Path | Description |
|---|---|---|
| POST | `/api/ask/` | Send a query (body: `{"query": "...", "session_id": "..."}`) |
| GET | `/api/health/` | Health check with data row counts |
| POST | `/api/reload-data/` | Reload Excel data from disk |
| DELETE | `/api/session/<id>/` | Clear conversation history |

## Deploy to Vercel

Push to GitHub and Vercel auto-deploys. Set environment variables in the Vercel dashboard (do **not** commit `.env`).
