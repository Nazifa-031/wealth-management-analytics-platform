"""
Shared utilities for report generation, used by both ask.py and
04_generate_report.py.

Generalized from a client-only engine into a mart-agnostic engine:
client / advisor / scheme / amc / executive all flow through the same
resolve -> fetch -> prompt -> LLM -> render pipeline. Only the config in
MART_CONFIG (and the executive-specific functions, since "executive" isn't
a single filterable entity) differ per mart.

>>> IMPORTANT <<<
The endpoint paths, id fields, and name fields below for advisor / scheme /
amc / executive are best-guess placeholders (marked with # ASSUMPTION).
The client mart mirrors the original working code exactly. Update the
ASSUMPTION lines to match your real API before relying on the other marts.
"""

import os
import re
import json
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:3000")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
OUTPUT_DIR = "reports"


# ---------------------------------------------------------------------------
# Generic API helper
# ---------------------------------------------------------------------------

def api_get(endpoint):
    resp = requests.get(f"{API_BASE_URL}{endpoint}", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]


# ---------------------------------------------------------------------------
# Mart configuration
#
# Each mart describes:
#   list_endpoint : where to GET all rows of this entity (for resolving by
#                    id or fuzzy name, same pattern as the old
#                    resolve_client_id)
#   id_field       : primary key field name on that entity
#   name_field     : human-readable name field, used for fuzzy matching and
#                    report titles
#   subtitle_fields: [(label, field), ...] shown under the report title
#   kpis           : [(label, field, fmt), ...] rendered as KPI cards.
#                    fmt is one of "currency", "number", "percent", "raw"
#   related        : {key: {"endpoint": ..., "fk": ...}} - other datasets
#                    filtered down to rows where row[fk] == entity_id
#   chart          : optional callable(bundle) -> svg string, appended
#                    after the related-data section
# ---------------------------------------------------------------------------

MART_CONFIG = {
    "client": {
        "list_endpoint": "/api/customers",
        "id_field": "client_id",
        "name_field": "client_name",
        "subtitle_fields": [
            ("Advisor", "advisor_name"),
            ("As of", "last_updated_date"),
        ],
        "kpis": [
            ("Total Invested", "total_investment", "currency"),
            ("Current Value", "current_value", "currency"),
            ("Gain / Loss", "gain_loss", "gain"),  # special: also shows gain_percent
            ("Active Schemes", "active_scheme_count", "number"),
        ],
        "related": {
            "sips": {"endpoint": "/api/sip-analytics", "fk": "client_id"},
            "redemptions": {"endpoint": "/api/redemptions", "fk": "client_id"},
        },
        "chart": lambda b: bar_chart_svg([
            ("Invested", (b["entity"].get("total_investment") or 0)),
            ("Current Value", (b["entity"].get("current_value") or 0)),
        ]),
    },

    # Confirmed against analytics.py: no numeric advisor_id exists anywhere
    # in the codebase - advisors are looked up by exact advisor_name, and
    # client rows link to their advisor via an "advisor_name" field (NOT
    # advisor_id). So id_field == name_field here: the "entity id" for this
    # mart IS the advisor's name string, and the related-clients fk matches
    # on that same name field.
    "advisor": {
        "list_endpoint": "/api/advisors",
        "id_field": "advisor_name",
        "name_field": "advisor_name",
        "subtitle_fields": [],
        "kpis": [
            ("Total AUM", "total_aum", "currency"),
            ("Total Clients", "total_clients", "number"),
            ("Total Revenue", "total_revenue", "currency"),
            ("Total Commission", "total_commission", "currency"),
            ("Active SIPs", "active_sip_count", "number"),
        ],
        "related": {
            "clients": {"endpoint": "/api/customers", "fk": "advisor_name"},
        },
        "chart": lambda b: bar_chart_svg([
            (c.get("client_name", "?")[:12], c.get("current_value") or 0)
            for c in b["related"].get("clients", [])[:8]
        ], color="#805ad5") if b["related"].get("clients") else "",
    },

    # Confirmed: no numeric scheme_id in analytics.py either - schemes are
    # matched by exact scheme_name. sip-analytics rows are confirmed to
    # carry both client_id and scheme_name (used by the client mart's SIP
    # section), so filtering by scheme_name here is solid.
    "scheme": {
        "list_endpoint": "/api/schemes",
        "id_field": "scheme_name",
        "name_field": "scheme_name",
        "subtitle_fields": [],
        "kpis": [
            ("Total AUM", "total_aum", "currency"),
            ("Average Return", "average_return", "percent"),
            ("Investors", "investor_count", "number"),
            ("Latest NAV", "latest_nav", "raw"),
        ],
        "related": {
            "sips": {"endpoint": "/api/sip-analytics", "fk": "scheme_name"},
        },
        # sip-analytics rows aren't confirmed to carry a client_name field
        # (only client_id + scheme_name + amounts were confirmed), so the
        # chart labels by client_id rather than guessing at a name field.
        "chart": lambda b: bar_chart_svg([
            (f"Client {s.get('client_id', '?')}", s.get("total_sip_amount") or 0)
            for s in b["related"].get("sips", [])[:8]
        ], color="#2c5282") if b["related"].get("sips") else "",
    },

    # Confirmed endpoint is singular "/api/amc" (not "/api/amcs"). Like
    # advisor/scheme, no numeric amc_id exists - matched by exact amc_name.
    # ASSUMPTION still open: whether /api/schemes rows carry an "amc_name"
    # field to link scheme -> amc. Not referenced anywhere in analytics.py,
    # so this is unverified - adjust the related fk below once confirmed.
    "amc": {
        "list_endpoint": "/api/amc",
        "id_field": "amc_name",
        "name_field": "amc_name",
        "subtitle_fields": [],
        "kpis": [
            ("Total AUM", "total_aum", "currency"),
            ("Average Return", "average_return", "percent"),
            ("Investors", "investor_count", "number"),
            ("Schemes", "scheme_count", "number"),
        ],
        "related": {
            "schemes": {"endpoint": "/api/schemes", "fk": "amc_name"},  # ASSUMPTION
        },
        "chart": lambda b: bar_chart_svg([
            (s.get("scheme_name", "?")[:12], s.get("total_aum") or 0)
            for s in b["related"].get("schemes", [])[:8]
        ], color="#2f855a") if b["related"].get("schemes") else "",
    },
}


# ---------------------------------------------------------------------------
# Resolution + fetching (client / advisor / scheme / amc)
# ---------------------------------------------------------------------------

def resolve_entity_id(mart, raw):
    """Same logic as the old resolve_client_id, generalized to any mart in
    MART_CONFIG: accept a raw numeric id, or fuzzy-match a name."""
    cfg = MART_CONFIG[mart]
    raw = raw.strip()
    rows = api_get(cfg["list_endpoint"])
    id_field = cfg["id_field"]
    name_field = cfg["name_field"]

    if raw.isdigit():
        for r in rows:
            if str(r.get(id_field)) == raw:
                return str(r.get(id_field))
        raise ValueError(f"No {mart} found with id {raw}")

    matches = [r for r in rows if raw.lower() in (r.get(name_field) or "").lower()]
    if len(matches) == 0:
        raise ValueError(
            f"No {mart} found matching '{raw}'. Try listing {cfg['list_endpoint']} to see real names."
        )
    if len(matches) > 1:
        names = "\n".join(f"  - {r[name_field]} ({id_field}: {r[id_field]})" for r in matches)
        raise ValueError(f"Multiple {mart}s match '{raw}':\n{names}\nBe more specific.")

    match = matches[0]
    print(f"Matched '{raw}' -> {match[name_field]} ({id_field}: {match[id_field]})")
    return str(match[id_field])


def fetch_mart_bundle(mart, entity_id):
    """Fetch the entity row plus all configured related datasets, filtered
    to this entity, for any mart in MART_CONFIG."""
    cfg = MART_CONFIG[mart]
    id_field = cfg["id_field"]

    rows = [r for r in api_get(cfg["list_endpoint"]) if str(r.get(id_field)) == str(entity_id)]
    if not rows:
        raise ValueError(f"No {mart} found with id {entity_id}")
    entity = rows[0]

    related = {}
    for rel_name, rel_cfg in cfg.get("related", {}).items():
        all_rows = api_get(rel_cfg["endpoint"])
        related[rel_name] = [
            r for r in all_rows if str(r.get(rel_cfg["fk"])) == str(entity_id)
        ]

    return {"mart": mart, "entity": entity, "related": related}


# ---------------------------------------------------------------------------
# Executive bundle. There is already a precomputed dashboard endpoint
# (confirmed in analytics.py: /api/executive-dashboard, returning a single
# summary row) - use that directly rather than re-aggregating client-by-
# client, so the figures match analytics.py / Databricks exactly. Top
# advisors/schemes are pulled separately purely for the report's charts.
# ---------------------------------------------------------------------------

def fetch_executive_bundle():
    exec_rows = api_get("/api/executive-dashboard")
    summary = exec_rows[0] if exec_rows else {}

    advisors = api_get(MART_CONFIG["advisor"]["list_endpoint"])
    schemes = api_get(MART_CONFIG["scheme"]["list_endpoint"])

    top_advisors = sorted(
        advisors, key=lambda a: a.get("total_aum") or 0, reverse=True
    )[:5]
    top_schemes = sorted(
        schemes, key=lambda s: s.get("total_aum") or 0, reverse=True
    )[:5]

    return {
        "mart": "executive",
        "summary": summary,
        "top_advisors": top_advisors,
        "top_schemes": top_schemes,
    }


# ---------------------------------------------------------------------------
# LLM prompt + call (shared across all marts)
# ---------------------------------------------------------------------------

def build_report_prompt(mart, bundle):
    if mart == "executive":
        data_for_prompt = bundle
        entity_desc = "the entire book of business across all clients, advisors and schemes"
    else:
        data_for_prompt = bundle
        entity_desc = f"this {mart}"

    return f"""You are a wealth management report writer. Using ONLY the
data below, write a report about {entity_desc}. Do not invent any numbers
not present in the data. Respond with STRICT JSON only, no markdown, no
extra text, matching exactly this shape:

{{{{
  "executive_summary": "2-3 sentences summarizing the overall position",
  "portfolio_commentary": "2-3 sentences interpreting the key value/gain figures",
  "sip_commentary": "2-3 sentences about SIP/scheme activity, or 'No data available.' if none",
  "risk_commentary": "2-3 sentences on risk/diversification/concentration",
  "recommendations": ["short actionable bullet 1", "short actionable bullet 2", "short actionable bullet 3"]
}}}}

--- DATA ---
{json.dumps(data_for_prompt, indent=2, default=str)}
--- END DATA ---
"""


def ask_llm_raw(prompt):
    if LLM_PROVIDER == "gemini":
        from google import genai
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text
    else:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


def get_narrative(mart, bundle):
    prompt = build_report_prompt(mart, bundle)
    raw = ask_llm_raw(prompt)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "executive_summary": raw[:400],
            "portfolio_commentary": "",
            "sip_commentary": "",
            "risk_commentary": "",
            "recommendations": [],
        }


# ---------------------------------------------------------------------------
# Chart helper (unchanged)
# ---------------------------------------------------------------------------

def bar_chart_svg(labels_values, width=500, height=220, color="#2c5282"):
    max_val = max([v for _, v in labels_values] + [1])
    bar_w = width / (len(labels_values) * 2) if labels_values else width
    bars = ""
    for i, (label, value) in enumerate(labels_values):
        bar_h = (value / max_val) * (height - 50)
        x = i * (bar_w * 2) + bar_w / 2
        y = height - bar_h - 30
        bars += (
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" fill="{color}" rx="3"/>'
            f'<text x="{x + bar_w/2}" y="{height - 12}" font-size="11" text-anchor="middle" fill="#333">{label}</text>'
            f'<text x="{x + bar_w/2}" y="{y - 6}" font-size="11" text-anchor="middle" fill="#111">{value:,.0f}</text>'
        )
    return f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">{bars}</svg>'


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

BASE_STYLE = """
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #f5f6f8; margin: 0; padding: 40px; color: #222; }
  .report { max-width: 800px; margin: 0 auto; background: white; border-radius: 10px; padding: 40px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }
  h1 { color: #1a2b4a; margin-bottom: 4px; }
  .subtitle { color: #666; margin-bottom: 30px; }
  h2 { color: #2c5282; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-top: 36px; }
  .kpi-row { display: flex; gap: 16px; flex-wrap: wrap; margin: 20px 0; }
  .kpi { background: #f0f4f8; border-radius: 8px; padding: 16px 20px; flex: 1; min-width: 140px; }
  .kpi .label { font-size: 12px; color: #666; text-transform: uppercase; }
  .kpi .value { font-size: 22px; font-weight: bold; color: #1a2b4a; }
  .gain-positive { color: #2f855a; }
  .gain-negative { color: #c53030; }
  ul.recs { padding-left: 20px; }
  ul.recs li { margin-bottom: 8px; }
  table.related { width: 100%; border-collapse: collapse; margin: 12px 0 24px; font-size: 13px; }
  table.related th, table.related td { text-align: left; padding: 6px 10px; border-bottom: 1px solid #eee; }
  table.related th { background: #f0f4f8; color: #444; }
  .footer { margin-top: 40px; font-size: 12px; color: #999; border-top: 1px solid #eee; padding-top: 16px; }
"""

HTML_SHELL = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>{style}</style>
</head>
<body>
<div class="report">
{body}
  <div class="footer">
    Generated by AnytimeInvest Analytics Platform. AI-assisted narrative,
    figures sourced directly from the data warehouse.
  </div>
</div>
</body>
</html>
"""


def _fmt(value, fmt):
    value = value or 0
    if fmt == "currency":
        return f"Rs.{value:,.0f}"
    if fmt == "percent":
        return f"{value:.1f}%"
    if fmt == "number":
        return f"{value:,.0f}"
    return str(value)


def _kpi_html(entity, kpis):
    cards = ""
    for label, field, fmt in kpis:
        if fmt == "gain":
            gain = entity.get(field) or 0
            gain_pct = entity.get("gain_percent") or 0
            gain_class = "gain-positive" if gain >= 0 else "gain-negative"
            cards += (
                f'<div class="kpi"><div class="label">{label}</div>'
                f'<div class="value {gain_class}">Rs.{gain:,.0f} ({gain_pct:.1f}%)</div></div>'
            )
        else:
            cards += (
                f'<div class="kpi"><div class="label">{label}</div>'
                f'<div class="value">{_fmt(entity.get(field), fmt)}</div></div>'
            )
    return cards


def _related_table_html(rows, max_rows=10):
    if not rows:
        return "<p>No records found.</p>"
    cols = list(rows[0].keys())[:6]  # keep tables readable
    header = "".join(f"<th>{c}</th>" for c in cols)
    body_rows = ""
    for r in rows[:max_rows]:
        body_rows += "<tr>" + "".join(f"<td>{r.get(c, '')}</td>" for c in cols) + "</tr>"
    more = f"<p><em>Showing {max_rows} of {len(rows)} records.</em></p>" if len(rows) > max_rows else ""
    return f"<table class='related'><tr>{header}</tr>{body_rows}</table>{more}"


def generate_entity_html(mart, bundle, narrative):
    """Generic renderer for client / advisor / scheme / amc reports."""
    cfg = MART_CONFIG[mart]
    entity = bundle["entity"]
    name = entity.get(cfg["name_field"], mart.title())

    subtitle_parts = [
        f"{label}: {entity.get(field, 'N/A')}" for label, field in cfg["subtitle_fields"]
    ]
    subtitle = " - ".join([mart.title()] + subtitle_parts)

    kpi_html = _kpi_html(entity, cfg["kpis"])

    related_sections = ""
    for rel_name, rows in bundle["related"].items():
        related_sections += f"<h2>{rel_name.title()}</h2>{_related_table_html(rows)}"

    chart_fn = cfg.get("chart")
    chart_html = chart_fn(bundle) if chart_fn else ""

    recs_html = "".join(f"<li>{r}</li>" for r in narrative.get("recommendations", []))

    body = f"""
  <h1>{name}</h1>
  <div class="subtitle">{subtitle}</div>

  <div class="kpi-row">{kpi_html}</div>

  <h2>Executive Summary</h2>
  <p>{narrative.get("executive_summary", "")}</p>

  <h2>Overview</h2>
  <p>{narrative.get("portfolio_commentary", "")}</p>
  {chart_html}

  <h2>Activity</h2>
  <p>{narrative.get("sip_commentary", "")}</p>
  {related_sections}

  <h2>Risk Analysis</h2>
  <p>{narrative.get("risk_commentary", "")}</p>

  <h2>Recommendations</h2>
  <ul class="recs">{recs_html or "<li>No recommendations generated.</li>"}</ul>
"""
    return HTML_SHELL.format(title=f"{mart.title()} Report - {name}", style=BASE_STYLE, body=body)


def generate_executive_html(bundle, narrative):
    s = bundle["summary"]
    kpi_html = "".join([
        f'<div class="kpi"><div class="label">Total AUM</div><div class="value">Rs.{(s.get("total_aum") or 0):,.0f}</div></div>',
        f'<div class="kpi"><div class="label">Total Investment</div><div class="value">Rs.{(s.get("total_investment") or 0):,.0f}</div></div>',
        f'<div class="kpi"><div class="label">Total Redemption</div><div class="value">Rs.{(s.get("total_redemption") or 0):,.0f}</div></div>',
        f'<div class="kpi"><div class="label">Total Revenue</div><div class="value">Rs.{(s.get("total_revenue") or 0):,.0f}</div></div>',
        f'<div class="kpi"><div class="label">Clients</div><div class="value">{(s.get("total_clients") or 0):,}</div></div>',
        f'<div class="kpi"><div class="label">Advisors</div><div class="value">{(s.get("total_advisors") or 0):,}</div></div>',
        f'<div class="kpi"><div class="label">Active Schemes</div><div class="value">{(s.get("active_schemes") or 0):,}</div></div>',
        f'<div class="kpi"><div class="label">Active SIPs</div><div class="value">{(s.get("active_sips") or 0):,}</div></div>',
    ])

    advisor_chart = bar_chart_svg([
        (a.get("advisor_name", "?")[:12], a.get("total_aum") or 0) for a in bundle["top_advisors"]
    ], color="#805ad5")
    scheme_chart = bar_chart_svg([
        (sc.get("scheme_name", "?")[:12], sc.get("aum") or 0) for sc in bundle["top_schemes"]
    ], color="#2c5282")

    recs_html = "".join(f"<li>{r}</li>" for r in narrative.get("recommendations", []))

    body = f"""
  <h1>Executive Summary Report</h1>
  <div class="subtitle">Firm-wide overview across all clients, advisors and schemes - As of {s.get("dashboard_date", "N/A")}</div>

  <div class="kpi-row">{kpi_html}</div>

  <h2>Executive Summary</h2>
  <p>{narrative.get("executive_summary", "")}</p>

  <h2>Portfolio Overview</h2>
  <p>{narrative.get("portfolio_commentary", "")}</p>

  <h2>Top Advisors by AUM</h2>
  {advisor_chart}
  {_related_table_html(bundle["top_advisors"])}

  <h2>Top Schemes by AUM</h2>
  {scheme_chart}
  {_related_table_html(bundle["top_schemes"])}

  <h2>Risk Analysis</h2>
  <p>{narrative.get("risk_commentary", "")}</p>

  <h2>Recommendations</h2>
  <ul class="recs">{recs_html or "<li>No recommendations generated.</li>"}</ul>
"""
    return HTML_SHELL.format(title="Executive Report", style=BASE_STYLE, body=body)


# ---------------------------------------------------------------------------
# Natural-language request parsing (shared by ask.py's chat loop and the
# 04_generate_report.py CLI, so both understand the same phrasing instead
# of each having their own copy of this logic).
# ---------------------------------------------------------------------------

REPORTABLE_MARTS = set(MART_CONFIG) | {"executive"}


def extract_report_target(question, mart):
    """
    Pull the identifier for the report out of free text, tailored to the
    mart already detected.

    client              -> numeric client id if present ("client 310"),
                            else a fuzzy name after "for"
    advisor/scheme/amc   -> a fuzzy name after "for", with the mart's own
                            keyword stripped off the front if the user
                            included it there ("for advisor John Doe" ->
                            "John Doe")
    executive            -> no identifier needed, returns None
    Returns None if nothing usable was found (e.g. no "for ..." clause).
    """
    if mart == "executive":
        return None

    if mart == "client":
        match = re.search(r"client\s+(?:id\s+)?(\d+)", question, re.IGNORECASE)
        if match:
            return match.group(1)

    match = re.search(r"for\s+(.+?)\s*[.?!]*$", question, re.IGNORECASE)
    if not match:
        return None

    target = match.group(1).strip()
    target = re.sub(rf"^(the\s+)?{re.escape(mart)}\s+", "", target, flags=re.IGNORECASE)
    return target.strip() or None


def parse_report_request(text):
    """
    Turn a free-form request like "generate a report for Rohan Mehta",
    "advisor report for Priya Shah", or "executive report" into
    (mart, identifier).

    Uses analytics.detect_mart() (imported lazily so callers that only
    need report generation aren't forced to depend on analytics.py) for
    mart detection, then extract_report_target() for the identifier.

    Falls back to treating the raw text itself as a client identifier
    when it doesn't look like a sentence at all - covers old-style bare
    input such as "101" or "Rohan Mehta" with no "for" clause and no
    report/mart keywords.
    """
    import analytics  # lazy import - avoids a hard dependency for callers
                       # that only ever call generate_report_for() directly

    text = text.strip()
    mart = analytics.detect_mart(text)
    if mart not in REPORTABLE_MARTS:
        mart = "client"

    if mart == "executive":
        return "executive", None

    identifier = extract_report_target(text, mart)
    if identifier:
        return mart, identifier

    # No "for ..." clause found. If this also doesn't look like a report
    # sentence at all, treat the whole input as a bare client identifier
    # (old-style CLI usage: just an id or a name, nothing else).
    if text and not re.search(r"\b(report|generate|create)\b", text, re.IGNORECASE):
        return "client", text

    return mart, None


def generate_report_from_text(text):
    """Convenience wrapper: parse a free-form request and generate the
    report in one call. Raises ValueError with a helpful message if the
    mart or identifier couldn't be determined."""
    mart, identifier = parse_report_request(text)
    if mart != "executive" and not identifier:
        raise ValueError(
            f"Could not determine which {mart} to generate a report for. "
            f"Try: 'generate a {mart} report for <name or id>'."
        )
    return generate_report_for(mart, identifier)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate_report_for(mart, raw_identifier=""):
    """
    mart: one of "client", "advisor", "scheme", "amc", "executive"
    raw_identifier: id or fuzzy name (ignored for "executive")
    """
    mart = mart.lower().strip()

    if mart == "executive":
        bundle = fetch_executive_bundle()
        narrative = get_narrative(mart, bundle)
        html = generate_executive_html(bundle, narrative)
        safe_id = "executive"
    elif mart in MART_CONFIG:
        entity_id = resolve_entity_id(mart, raw_identifier)
        bundle = fetch_mart_bundle(mart, entity_id)
        narrative = get_narrative(mart, bundle)
        html = generate_entity_html(mart, bundle, narrative)
        safe_id = re.sub(r'[:\\/*?"<>|]', "-", str(entity_id))
    else:
        raise ValueError(f"Unknown mart '{mart}'. Choose one of: {list(MART_CONFIG) + ['executive']}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{mart}_{safe_id}_report.html")
    with open(out_path, "w") as f:
        f.write(html)
    return out_path