# Wealth Management Analytics Platform

## Structure of Execution

```text
wealth-management-analytics-platform/
│
├── databricks-notebooks/
│   ├── 00_setup.py
│   ├── 01_data_generation.py
│   ├── 02_bronze_layer.py
│   ├── 03_silver_layer.py
│   ├── 04_warehouse_layer.py
│   ├── 05_warehouse_checklist.py
│   ├── 06_data_marts.py
│   └── 07_dashboard_queries.sql
│
├── databricks-api/
│   ├── server.js
│   ├── package.json
│   ├── .gitignore
│   └── (Do NOT include .env)
│
└── rag-pipeline/
    ├── prepare.py
    ├── build2.py
    ├── ask3.py
    ├── genreport4.py
    └── (Do NOT include .env)
```

## Execution

### 1. Databricks Notebooks

Run the notebooks in numerical order:

1. `00_setup.py`
2. `01_data_generation.py`
3. `02_bronze_layer.py`
4. `03_silver_layer.py`
5. `04_warehouse_layer.py`
6. `05_warehouse_checklist.py`
7. `06_data_marts.py`
8. `07_dashboard_queries.sql`

### 2. API

1. Download all API files into the **databricks-api** folder.
2. Open a terminal in that folder.
3. Install dependencies:

```bash
npm install
```

4. Start the API:

```bash
npm start
```

The Express server will start on the configured port.

### 3. RAG Pipeline

Create a folder named **rag-pipeline** and copy the following files into it:

* `prepare.py`
* `build2.py`
* `ask3.py`
* `genreport4.py`

Run them in the following order:

```text
1. prepare.py
2. build2.py
3. ask3.py
4. genreport4.py
```

> **Note:** Ensure the API is running before executing the RAG pipeline, as it retrieves live data from the API.


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

