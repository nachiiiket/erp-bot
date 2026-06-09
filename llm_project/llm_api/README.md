# Sales Analytics AI Agent — Setup Guide

## File Structure

Paste files into your DRF project like this:

```
llm_project/
├── llm_api/
│   ├── data/                          ← create this folder, put Excel files here
│   │   ├── Sales_Order__DynaRep...xlsx
│   │   ├── Sales_Order_Details__DynaRep...xlsx
│   │   └── Sales_Invovoice.xlsx
│   ├── data_loader.py                 ← new
│   ├── analytics_tools.py             ← new
│   ├── agent.py                       ← new
│   ├── views.py                       ← replace
│   └── urls.py                        ← replace
└── llm_project/
    └── urls.py                        ← add include() for llm_api.urls
```

## llm_project/urls.py — add this

```python
from django.urls import path, include

urlpatterns = [
    path('api/', include('llm_api.urls')),
]
```

## Install dependencies

```bash
pip install anthropic pandas openpyxl numpy djangorestframework
```

## Environment variable

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export SALES_DATA_DIR=/path/to/llm_api/data   # optional, defaults to llm_api/data/
```

## API Endpoints

| Method | URL | Purpose |
|--------|-----|---------|
| POST | /api/ask/ | Main agent query |
| GET | /api/health/ | Check data loaded |
| POST | /api/reload-data/ | Reload Excel files |
| DELETE | /api/session/{id}/ | Clear conversation |

## Example requests

### Single query
```json
POST /api/ask/
{
  "query": "What are the top 5 customers by revenue?"
}
```

### Multi-turn conversation
```json
POST /api/ask/
{
  "query": "Show me top 3 products",
  "session_id": "user-123"
}

POST /api/ask/
{
  "query": "Now which of those are declining?",
  "session_id": "user-123"
}
```

## Sample queries the agent handles

- "Top 10 products sold by revenue"
- "Top 4 customers by order count"
- "Which products should we discontinue and why?"
- "Which customers are declining?"
- "Where is volume growing?"
- "Give me a full analysis of V.Ships"
- "What is the order to invoice gap?"
- "Show me low volume / slow moving products"
- "Overall revenue summary"
- "Which customers should we focus more on?"
- "Payment behavior of Dynacom" (will request data upload)
- "Are there any sales returns issues?" (will request data upload)

## Adding payment / returns data later

1. Add your Excel files to `llm_api/data/`
2. Add a new entry to `DATA_FILES` in `data_loader.py`
3. Implement the real logic in `get_payment_behavior()` and `get_return_analysis()` in `analytics_tools.py`
4. Call `POST /api/reload-data/` to refresh cache
