"""
Step 1: Prepare Documents - chunking + metadata, across all 8 marts.

Each chunk now contains BOTH a structured field block (Field: value lines)
and a narrative paragraph, plus a keywords line. Structured fields help
the embedding model and the LLM read exact figures without having to parse
prose; the narrative helps semantic/descriptive matching; keywords help
retrieval for questions phrased differently than the data itself.

Metadata per chunk includes the mart type plus the relevant id AND name
fields, so ChromaDB can filter (e.g. where={"advisor_id": 21}) instead of
relying on similarity search alone.
"""

import os
import re
import json
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:3000")
OUTPUT_DIR = "documents"


def fetch(endpoint):
    resp = requests.get(f"{API_BASE_URL}{endpoint}", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]


def fields_block(pairs):
    return "\n".join(f"{label}: {value}" for label, value in pairs)


def client_text(c):
    gain_word = "gained" if (c.get("gain_loss") or 0) >= 0 else "lost"
    fields = fields_block([
        ("Client ID", c.get("client_id")),
        ("Client Name", c.get("client_name")),
        ("Advisor Name", c.get("advisor_name")),
        ("Total Investment", c.get("total_investment")),
        ("Current Value", c.get("current_value")),
        ("Gain Loss", c.get("gain_loss")),
        ("Gain Percent", c.get("gain_percent")),
        ("Active Scheme Count", c.get("active_scheme_count")),
        ("Total Units", c.get("total_units")),
        ("Last Updated", c.get("last_updated_date")),
    ])
    narrative = (
        f"Client {c.get('client_name')} (ID: {c.get('client_id')}) is managed by "
        f"advisor {c.get('advisor_name')}. They have invested a total of "
        f"Rs.{c.get('total_investment')}, currently worth Rs.{c.get('current_value')}. "
        f"This portfolio has {gain_word} Rs.{abs(c.get('gain_loss') or 0)}, a change of "
        f"{c.get('gain_percent')}%. They hold {c.get('active_scheme_count')} active "
        f"schemes, totaling {c.get('total_units')} units."
    )
    keywords = "Keywords: client, customer, portfolio, investment, gain, loss, holdings"
    return f"{fields}\n\nNarrative: {narrative}\n\n{keywords}"


def advisor_text(a):
    fields = fields_block([
        ("Advisor ID", a.get("advisor_id")),
        ("Advisor Name", a.get("advisor_name")),
        ("Total Clients", a.get("total_clients")),
        ("Total AUM", a.get("total_aum")),
        ("Total Commission", a.get("total_commission")),
        ("Total Revenue", a.get("total_revenue")),
        ("Average Client AUM", a.get("average_client_aum")),
        ("Active SIP Count", a.get("active_sip_count")),
        ("Last Updated", a.get("last_updated_date")),
    ])
    narrative = (
        f"Advisor {a.get('advisor_name')} manages {a.get('total_clients')} clients "
        f"with total AUM of Rs.{a.get('total_aum')}, earning Rs.{a.get('total_commission')} "
        f"in commissions and Rs.{a.get('total_revenue')} in total revenue."
    )
    keywords = "Keywords: advisor, agent, broker, AUM, commission, revenue, clients managed"
    return f"{fields}\n\nNarrative: {narrative}\n\n{keywords}"


def scheme_text(s):
    fields = fields_block([
        ("Scheme ID", s.get("scheme_id")),
        ("Scheme Name", s.get("scheme_name")),
        ("AMC Name", s.get("amc_name")),
        ("Category", s.get("category_name")),
        ("Investor Count", s.get("investor_count")),
        ("Total AUM", s.get("total_aum")),
        ("Average Return", s.get("average_return")),
        ("Units Held", s.get("units_held")),
        ("Latest NAV", s.get("latest_nav")),
        ("Last Updated", s.get("last_updated_date")),
    ])
    narrative = (
        f"Scheme {s.get('scheme_name')}, offered by {s.get('amc_name')} in the "
        f"{s.get('category_name')} category, has {s.get('investor_count')} investors "
        f"and Rs.{s.get('total_aum')} in AUM, with an average return of "
        f"{s.get('average_return')}%."
    )
    keywords = "Keywords: scheme, fund, mutual fund, NAV, return, AMC, category"
    return f"{fields}\n\nNarrative: {narrative}\n\n{keywords}"


def revenue_text(r):
    fields = fields_block([
        ("Advisor ID", r.get("advisor_id")),
        ("Advisor Name", r.get("advisor_name")),
        ("Month", r.get("month")),
        ("Year", r.get("year")),
        ("Brokerage Amount", r.get("brokerage_amount")),
        ("Trail Commission", r.get("trail_commission")),
        ("Total Revenue", r.get("total_revenue")),
    ])
    narrative = (
        f"In month {r.get('month')} of {r.get('year')}, advisor {r.get('advisor_name')} "
        f"generated Rs.{r.get('brokerage_amount')} in brokerage and "
        f"Rs.{r.get('trail_commission')} in trail commission."
    )
    keywords = "Keywords: revenue, commission, brokerage, trail, monthly earnings"
    return f"{fields}\n\nNarrative: {narrative}\n\n{keywords}"


def sip_text(s):
    fields = fields_block([
        ("Client ID", s.get("client_id")),
        ("Client Name", s.get("client_name")),
        ("Scheme Name", s.get("scheme_name")),
        ("Installment Count", s.get("installment_count")),
        ("Total SIP Amount", s.get("total_sip_amount")),
        ("Total Units", s.get("total_units")),
        ("Latest NAV", s.get("latest_nav")),
        ("Current Value", s.get("current_value")),
    ])
    narrative = (
        f"Client {s.get('client_name')} has a SIP in {s.get('scheme_name')} with "
        f"{s.get('installment_count')} installments totaling Rs.{s.get('total_sip_amount')}."
    )
    keywords = "Keywords: SIP, systematic investment plan, installment, recurring investment"
    return f"{fields}\n\nNarrative: {narrative}\n\n{keywords}"


def redemption_text(r):
    fields = fields_block([
        ("Client ID", r.get("client_id")),
        ("Client Name", r.get("client_name")),
        ("Scheme Name", r.get("scheme_name")),
        ("Redemption Count", r.get("redemption_count")),
        ("Redeemed Amount", r.get("redeemed_amount")),
        ("Redeemed Units", r.get("redeemed_units")),
        ("Redemption Month", r.get("redemption_month")),
        ("Redemption Year", r.get("redemption_year")),
    ])
    narrative = (
        f"Client {r.get('client_name')} redeemed from {r.get('scheme_name')} "
        f"{r.get('redemption_count')} time(s), withdrawing Rs.{r.get('redeemed_amount')}."
    )
    keywords = "Keywords: redemption, withdrawal, redeemed units, exit"
    return f"{fields}\n\nNarrative: {narrative}\n\n{keywords}"


def amc_text(a):
    fields = fields_block([
        ("AMC ID", a.get("amc_id")),
        ("AMC Name", a.get("amc_name")),
        ("Total AUM", a.get("total_aum")),
        ("Investor Count", a.get("investor_count")),
        ("Scheme Count", a.get("scheme_count")),
        ("Average Return", a.get("average_return")),
    ])
    narrative = (
        f"{a.get('amc_name')} has Rs.{a.get('total_aum')} in AUM across "
        f"{a.get('scheme_count')} schemes, with {a.get('investor_count')} investors."
    )
    keywords = "Keywords: AMC, asset management company, fund house"
    return f"{fields}\n\nNarrative: {narrative}\n\n{keywords}"


def executive_text(e):
    fields = fields_block([
        ("Dashboard Date", e.get("dashboard_date")),
        ("Total Clients", e.get("total_clients")),
        ("Total Advisors", e.get("total_advisors")),
        ("Total AUM", e.get("total_aum")),
        ("Total Investment", e.get("total_investment")),
        ("Total Redemption", e.get("total_redemption")),
        ("Total Revenue", e.get("total_revenue")),
        ("Active SIPs", e.get("active_sips")),
        ("Active Schemes", e.get("active_schemes")),
    ])
    narrative = (
        f"As of {e.get('dashboard_date')}, the company has {e.get('total_clients')} "
        f"clients, Rs.{e.get('total_aum')} in AUM, and Rs.{e.get('total_revenue')} "
        f"in total revenue."
    )
    keywords = "Keywords: executive summary, company overview, business health, overall"
    return f"{fields}\n\nNarrative: {narrative}\n\n{keywords}"


def client_meta(row):
    return {"client_id": row.get("client_id"), "client_name": row.get("client_name")}


def advisor_meta(row):
    return {"advisor_id": row.get("advisor_id"), "advisor_name": row.get("advisor_name")}


def scheme_meta(row):
    return {"scheme_id": row.get("scheme_id"), "scheme_name": row.get("scheme_name")}


def revenue_meta(row):
    return {
        "advisor_id": row.get("advisor_id"), "advisor_name": row.get("advisor_name"),
        "year": row.get("year"), "month": row.get("month"),
    }


def sip_meta(row):
    return {
        "client_id": row.get("client_id"), "client_name": row.get("client_name"),
        "scheme_name": row.get("scheme_name"),
    }


def redemption_meta(row):
    return {
        "client_id": row.get("client_id"), "client_name": row.get("client_name"),
        "scheme_name": row.get("scheme_name"),
        "year": row.get("redemption_year"), "month": row.get("redemption_month"),
    }


def amc_meta(row):
    return {"amc_id": row.get("amc_id"), "amc_name": row.get("amc_name")}


def executive_meta(row):
    return {"dashboard_date": row.get("dashboard_date")}


MARTS = {
    "client": {"endpoint": "/api/customers", "id_fields": ["client_id"], "text_fn": client_text, "meta_fn": client_meta},
    "advisor": {"endpoint": "/api/advisors", "id_fields": ["advisor_id"], "text_fn": advisor_text, "meta_fn": advisor_meta},
    "scheme": {"endpoint": "/api/schemes", "id_fields": ["scheme_id"], "text_fn": scheme_text, "meta_fn": scheme_meta},
    "revenue": {"endpoint": "/api/revenue", "id_fields": ["advisor_id", "year", "month"], "text_fn": revenue_text, "meta_fn": revenue_meta},
    "sip": {"endpoint": "/api/sip-analytics", "id_fields": ["client_id", "scheme_name"], "text_fn": sip_text, "meta_fn": sip_meta},
    "redemption": {"endpoint": "/api/redemptions", "id_fields": ["client_id", "scheme_name", "redemption_year", "redemption_month"], "text_fn": redemption_text, "meta_fn": redemption_meta},
    "amc": {"endpoint": "/api/amc", "id_fields": ["amc_id"], "text_fn": amc_text, "meta_fn": amc_meta},
    "executive": {"endpoint": "/api/executive-dashboard", "id_fields": ["dashboard_date"], "text_fn": executive_text, "meta_fn": executive_meta},
}


def make_chunk_id(mart_name, row, id_fields, fallback_index):
    parts = [str(row.get(f, fallback_index)) for f in id_fields]
    raw_id = f"{mart_name}_" + "_".join(parts)
    # Windows forbids : \ / * ? " < > | in filenames - the executive mart's
    # dashboard_date (an ISO timestamp like 2026-07-02T00:00:00.000Z) has
    # colons, which crashed file writes on Windows. Replace anything unsafe.
    return re.sub(r'[:\\/*?"<>|]', "-", raw_id)


def clean_metadata(meta):
    return {k: v for k, v in meta.items() if v is not None}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    manifest = []

    for mart_name, cfg in MARTS.items():
        try:
            rows = fetch(cfg["endpoint"])
        except Exception as e:
            print(f"Skipping '{mart_name}' ({cfg['endpoint']}) - request failed: {e}")
            continue

        for i, row in enumerate(rows):
            chunk_id = make_chunk_id(mart_name, row, cfg["id_fields"], i)
            text = cfg["text_fn"](row)
            metadata = {"mart": mart_name, **clean_metadata(cfg["meta_fn"](row))}

            with open(os.path.join(OUTPUT_DIR, f"{chunk_id}.txt"), "w") as f:
                f.write(text)

            manifest.append({"chunk_id": chunk_id, "mart": mart_name, "text": text, "metadata": metadata})

        print(f"{mart_name:12s} -> {len(rows)} chunks from {cfg['endpoint']}")

    with open(os.path.join(OUTPUT_DIR, "_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Wrote {len(manifest)} total chunks across {len(MARTS)} marts to '{OUTPUT_DIR}/'")


if __name__ == "__main__":
    main()