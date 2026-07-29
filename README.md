# wealth-management-analytics-platform

Structure of Execution
 wealth-management-analytics-platform/
├── databricks-notebooks/
│   ├── 00_setup.py
│   ├── 01_data_generation.py
│   ├── 02_bronze_layer.py
│   ├── 03_silver_layer.py
│   ├── 04_warehouse_layer.py
│   ├── 05_warehouse_checklist.py
│   ├── 06_data_marts.py
│   └── 07_dashboard_queries.sql
├── databricks-api/          (your Express API — server.js, package.json, .gitignore, NOT .env) API FILES
└── rag-pipeline/            (your Python RAG — all .py files, NOT .env) RAG FILES

# Wealth Report Generator

Generates AI-narrated HTML investment reports for any mart in the system
— client, advisor, scheme, AMC, or a firm-wide executive summary — from
either a chat interface (`ask.py`) or a standalone CLI (`04_generate_report.py`).

Both share one engine (`report_utils.py`), so a phrase like
`"create a report for Rohan Mehta"` is understood identically no matter
which one you type it into.

---

## Files

| File | What it is |
|---|---|
| `report_utils.py` | The engine. All mart config, data fetching, AI narrative generation, HTML rendering, and natural-language request parsing live here. |
| `ask.py` | Interactive chat loop. Routes each question to report generation, analytical computation (`analytics.py`), or RAG-based Q&A. |
| `04_generate_report.py` | Standalone CLI, report generation only. No embedding model or ChromaDB required, so it starts instantly. |
| `analytics.py` | *(not modified here)* Exact-computation engine for Top-N / totals / averages / rankings, and the mart-keyword detector (`detect_mart`) that report parsing also reuses. |

---

## Setup

1. **Install dependencies** (in addition to whatever `ask.py`'s RAG path needs):
   ```
   pip install requests python-dotenv google-genai
   ```
   Use `anthropic` instead of `google-genai` if you set `LLM_PROVIDER=anthropic`.

2. **Create a `.env` file** in the same folder as these scripts:
   ```dotenv
   API_BASE_URL=http://localhost:3000
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=your_real_key_here
   GEMINI_MODEL=gemini-3.1-flash-lite
   ```
   No quotes, no spaces around `=`. Get a key at https://aistudio.google.com/apikey.

   `report_utils.py` loads this `.env` itself (`load_dotenv()` at import
   time), so it works whether you're running `ask.py` or
   `04_generate_report.py` directly — you don't need to add
   `load_dotenv()` to any new script that imports `report_utils`.

3. **Start your backend API** (whatever serves `/api/customers`,
   `/api/advisors`, etc. on `API_BASE_URL`). Report generation makes live
   HTTP calls to it — if it's not running you'll get a
   `ConnectionRefusedError`.

---

## Usage

### Chat loop (`ask.py`)
```
python ask.py
Question: create a report for Rohan Mehta
Question: advisor report for Priya Shah
Question: top 5 clients by current value
```
Handles reports, analytical queries, and descriptive/RAG questions all in
one prompt.

### Standalone CLI (`04_generate_report.py`)
Interactive mode:
```
python 04_generate_report.py
Report request: create a report for Rohan Mehta
Report request: executive report
Report request: quit
```
One-shot mode (for scripts/cron):
```
python 04_generate_report.py create a report for Rohan Mehta
python 04_generate_report.py executive
python 04_generate_report.py 101
```

### Example phrasings that work
```
create a report for Rohan Mehta
generate a report for client 310
advisor report for Priya Shah
scheme report for Bluechip Growth Fund
report for amc HDFC Mutual Fund
executive report
101                          (bare id/name, old-style, defaults to client)

browser.

