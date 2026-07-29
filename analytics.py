"""
Analytical query engine - COMPLETE for ALL 8 MARTS
Handles: Client, Advisor, Scheme, Revenue, SIP, Redemption, AMC, Executive
"""

import re
import os
import requests
from collections import defaultdict
from typing import Tuple, Dict, List, Optional

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:3000")

MART_ENDPOINTS = {
    "client": "/api/customers",
    "advisor": "/api/advisors",
    "scheme": "/api/schemes",
    "revenue": "/api/revenue",
    "sip": "/api/sip-analytics",
    "redemption": "/api/redemptions",
    "amc": "/api/amc",
    "executive": "/api/executive-dashboard",
}

NAME_FIELD = {
    "advisor": "advisor_name",
    "scheme": "scheme_name",
    "client": "client_name",
    "revenue": "advisor_name",
    "sip": "scheme_name",
    "redemption": "scheme_name",
    "amc": "amc_name",
}

MART_METRICS = {
    "advisor": [
        ("average client aum", "average_client_aum"), ("average aum", "average_client_aum"),
        ("aum", "total_aum"), ("revenue", "total_revenue"), ("commission", "total_commission"),
        ("clients", "total_clients"), ("sip", "active_sip_count"),
    ],
    "client": [
        ("value", "current_value"), ("investment", "total_investment"), ("gain", "gain_percent"),
        ("loss", "gain_loss"), ("unit", "total_units"), ("profit", "gain_loss"), ("success", "gain_percent"),
    ],
    "scheme": [
        ("return", "average_return"), ("aum", "total_aum"), ("investor", "investor_count"),
        ("unit", "units_held"), ("nav", "latest_nav"),
    ],
    "revenue": [
        ("brokerage", "brokerage_amount"), ("trail", "trail_commission"), ("revenue", "total_revenue"),
    ],
    "sip": [
        ("amount", "total_sip_amount"), ("inflow", "total_sip_amount"), ("investment", "total_sip_amount"),
        ("installment", "installment_count"), ("value", "current_value"), ("unit", "total_units"),
        ("nav", "latest_nav"),
    ],
    "redemption": [
        ("amount", "redeemed_amount"), ("unit", "redeemed_units"), ("count", "redemption_count"),
    ],
    "amc": [
        ("aum", "total_aum"), ("assets", "total_aum"), ("return", "average_return"),
        ("investor", "investor_count"), ("scheme", "scheme_count"),
    ],
}

ASCENDING_WORDS = ["lowest", "worst", "least", "bottom", "smallest", "minimum"]
ANALYTICAL_WORDS = [
    "top", "highest", "lowest", "best", "worst", "most", "least", "total",
    "sum", "average", "avg", "count", "how many", "rank", "ranking", "bottom",
    "success", "profit", "performance", "ratio", "compare", "comparison",
    "which", "who", "what", "list", "show", "find", "get",
]

_cache = {}


def is_analytical(question: str) -> bool:
    q = question.lower()
    if any(word in q for word in ANALYTICAL_WORDS):
        return True
    if re.search(r'\d+', q) and any(word in q for word in ["aum", "revenue", "profit", "gain", "loss"]):
        return True
    return False


def fetch_mart(mart: str) -> List[Dict]:
    if mart in _cache:
        return _cache[mart]
    try:
        resp = requests.get(f"{API_BASE_URL}{MART_ENDPOINTS[mart]}", timeout=30)
        resp.raise_for_status()
        data = resp.json()
        result = data if isinstance(data, list) else [data]
        _cache[mart] = result
        return result
    except Exception as e:
        print(f"Error fetching {mart}: {e}")
        return []


def detect_mart(question: str) -> Optional[str]:
    q = question.lower()
    if any(word in q for word in ["amc", "asset management", "fund house"]):
        return "amc"
    if any(word in q for word in ["advisor", "adviser", "agent", "broker"]):
        return "advisor"
    if any(word in q for word in ["sip", "installment"]):
        return "sip"
    if any(word in q for word in ["redemption", "redeemed", "withdrawal"]):
        return "redemption"
    if any(word in q for word in ["revenue", "commission", "brokerage", "trail"]):
        return "revenue"
    if any(word in q for word in ["scheme", "fund", "nav"]):
        return "scheme"
    if any(word in q for word in ["company", "overall", "executive", "summary", "business"]):
        return "executive"
    if any(word in q for word in ["client", "customer", "portfolio", "holding"]):
        return "client"
    return None


def detect_metric(question: str, mart: str) -> Optional[str]:
    q = question.lower()
    if "nav" in q and mart == "scheme":
        return "latest_nav"
    if "unit" in q:
        return "total_units" if mart == "client" else "units_held"
    for keyword, column in MART_METRICS.get(mart, []):
        if keyword in q:
            return column
    defaults = {
        "advisor": "total_aum", "client": "current_value", "scheme": "average_return",
        "revenue": "total_revenue", "sip": "total_sip_amount", "redemption": "redeemed_amount",
        "amc": "total_aum", "executive": None,
    }
    return defaults.get(mart)


def detect_top_n(question: str) -> int:
    match = re.search(r"top\s*(\d+)", question.lower())
    if match:
        return int(match.group(1))
    return 10


def detect_order(question: str) -> str:
    q = question.lower()
    if any(w in q for w in ASCENDING_WORDS):
        return "asc"
    return "desc"


def aggregate(rows: List[Dict], name_field: str, metric_field: str) -> Dict:
    totals = defaultdict(float)
    for row in rows:
        name = row.get(name_field)
        value = row.get(metric_field)
        if name is None or value is None:
            continue
        try:
            totals[name] += float(value)
        except (ValueError, TypeError):
            continue
    return totals


def filter_by_threshold(rows: List[Dict], field: str, threshold: float, operator: str = "gt") -> List[Dict]:
    filtered = []
    for row in rows:
        val = row.get(field, 0)
        if val is None:
            continue
        try:
            val = float(val)
            if operator == "gt" and val > threshold:
                filtered.append(row)
            elif operator == "gte" and val >= threshold:
                filtered.append(row)
            elif operator == "lt" and val < threshold:
                filtered.append(row)
            elif operator == "lte" and val <= threshold:
                filtered.append(row)
        except Exception:
            continue
    return filtered


def get_client_by_id(client_id) -> Optional[Dict]:
    clients = fetch_mart("client")
    for c in clients:
        if str(c.get("client_id")) == str(client_id):
            return c
    return None


def format_client_details(c: Dict) -> str:
    gain = c.get("gain_loss", 0) or 0
    lines = [
        "CLIENT DETAILS",
        "=" * 50,
        f"Client: {c.get('client_name')}",
        f"ID: {c.get('client_id')}",
        f"Advisor: {c.get('advisor_name')}",
        f"Total Investment: Rs.{(c.get('total_investment') or 0):,.2f}",
        f"Current Value: Rs.{(c.get('current_value') or 0):,.2f}",
        f"Gain/Loss: Rs.{gain:,.2f} ({(c.get('gain_percent') or 0):.1f}%)",
        f"Active Schemes: {c.get('active_scheme_count', 0)}",
        f"Total Units: {(c.get('total_units') or 0):,.2f}",
        f"Last Updated: {c.get('last_updated_date', 'N/A')}",
    ]
    return "\n".join(lines)


def answer_client_query(client_id: int, question: str) -> Tuple[Optional[str], Dict]:
    """
    Handles ANY question that names a specific client id: both
    "give me full details" style questions AND single-field questions
    like "how many units does client 310 hold". This runs BEFORE the
    generic count/aggregate branches so a specific-client question never
    gets mistaken for a mart-wide aggregate question.
    """
    client = get_client_by_id(client_id)
    if not client:
        return f"No client found with ID {client_id}.", {"client_id": client_id, "found": False}

    q = question.lower()
    name = client.get("client_name")

    # "Summarize client X including advisor, schemes, SIPs..." mentions
    # several field keywords at once - that's a request for the FULL
    # picture, not a shortcut for whichever field keyword appears first.
    wants_full_summary = any(w in q for w in ["summar", "including", "full detail", "everything about"])

    if not wants_full_summary and "unit" in q:
        return f"Client {name} (ID: {client_id}) holds {(client.get('total_units') or 0):,.2f} units.", \
            {"client_id": client_id, "field": "total_units"}
    if not wants_full_summary and ("current value" in q or ("value" in q and "current" in q)):
        return f"Client {name} (ID: {client_id}) has a current portfolio value of Rs.{(client.get('current_value') or 0):,.2f}.", \
            {"client_id": client_id, "field": "current_value"}
    if not wants_full_summary and ("investment" in q or "invested" in q):
        return f"Client {name} (ID: {client_id}) has invested a total of Rs.{(client.get('total_investment') or 0):,.2f}.", \
            {"client_id": client_id, "field": "total_investment"}
    if not wants_full_summary and ("gain" in q or "loss" in q or "profit" in q):
        return (f"Client {name} (ID: {client_id}) has a gain/loss of "
                f"Rs.{(client.get('gain_loss') or 0):,.2f} ({(client.get('gain_percent') or 0):.1f}%).", \
            {"client_id": client_id, "field": "gain_loss"})
    if not wants_full_summary and "advisor" in q:
        return f"Client {name} (ID: {client_id}) is managed by advisor {client.get('advisor_name')}.", \
            {"client_id": client_id, "field": "advisor_name"}
    if not wants_full_summary and ("scheme" in q and "how many" in q or ("scheme count" in q)):
        return f"Client {name} (ID: {client_id}) holds {client.get('active_scheme_count', 0)} active schemes.", \
            {"client_id": client_id, "field": "active_scheme_count"}

    # No specific field detected - return full details (covers "summary",
    # "portfolio", "details", "who", "what is", or just "client 101" alone).
    # Also pulls in SIP and redemption data for this client, since
    # "summarize client X including SIPs and redemptions" needs more than
    # just the client_portfolio_summary row.
    details = format_client_details(client)

    sips = [s for s in fetch_mart("sip") if str(s.get("client_id")) == str(client_id)]
    if sips:
        sip_lines = ["", "SIP ACTIVITY", "-" * 30]
        for s in sips:
            sip_lines.append(
                f"  {s.get('scheme_name')}: {s.get('installment_count')} installments, "
                f"Rs.{(s.get('total_sip_amount') or 0):,.2f} invested"
            )
        details += "\n" + "\n".join(sip_lines)

    redemptions = [r for r in fetch_mart("redemption") if str(r.get("client_id")) == str(client_id)]
    if redemptions:
        red_lines = ["", "REDEMPTION ACTIVITY", "-" * 30]
        for r in redemptions:
            red_lines.append(
                f"  {r.get('scheme_name')}: Rs.{(r.get('redeemed_amount') or 0):,.2f} redeemed "
                f"({r.get('redemption_count')} time(s))"
            )
        details += "\n" + "\n".join(red_lines)

    return details, {"client_id": client_id, "found": True}


def get_advisor_details(advisor_name: str) -> Dict:
    advisors = fetch_mart("advisor")
    for a in advisors:
        if a.get("advisor_name") == advisor_name:
            return a
    return {}


def get_scheme_details(scheme_name: str) -> Dict:
    schemes = fetch_mart("scheme")
    for s in schemes:
        if s.get("scheme_name") == scheme_name:
            return s
    return {}


def calculate_advisor_client_profit(advisor_rows: List[Dict], client_rows: List[Dict]) -> Dict:
    advisor_profits = {}
    clients_by_advisor = defaultdict(list)
    for client in client_rows:
        advisor = client.get("advisor_name")
        if advisor:
            clients_by_advisor[advisor].append(client)

    for advisor_name, clients in clients_by_advisor.items():
        total_profit, total_clients, total_aum, positive_gains = 0, 0, 0, 0
        for client in clients:
            gain = client.get("gain_loss", 0)
            if gain:
                total_profit += float(gain)
                total_clients += 1
                total_aum += float(client.get("current_value", 0) or 0)
                if float(gain) > 0:
                    positive_gains += 1
        advisor_info = next((a for a in advisor_rows if a.get("advisor_name") == advisor_name), {})
        advisor_profits[advisor_name] = {
            "total_profit": total_profit, "total_clients": total_clients,
            "positive_clients": positive_gains,
            "success_ratio": (positive_gains / total_clients * 100) if total_clients > 0 else 0,
            "avg_profit": total_profit / total_clients if total_clients > 0 else 0,
            "total_aum": total_aum,
            "revenue": advisor_info.get("total_revenue", 0),
            "commission": advisor_info.get("total_commission", 0),
            "active_sips": advisor_info.get("active_sip_count", 0),
        }
    return advisor_profits


def find_advisor_for_best_client() -> Optional[str]:
    clients = fetch_mart("client")
    if not clients:
        return None
    best_client = max(clients, key=lambda x: float(x.get("gain_loss", 0) or 0))
    advisor_name = best_client.get("advisor_name")
    if not advisor_name:
        return None
    advisors = fetch_mart("advisor")
    advisor = next((a for a in advisors if a.get("advisor_name") == advisor_name), {})
    lines = [
        "ADVISOR FOR HIGHEST-GAIN CLIENT", "=" * 60,
        f"Client: {best_client.get('client_name')}",
        f"Client ID: {best_client.get('client_id')}",
        f"Gain: Rs.{(best_client.get('gain_loss') or 0):,.2f} ({(best_client.get('gain_percent') or 0):.1f}%)",
        "",
        f"Advisor: {advisor_name}",
        f"Total AUM: Rs.{(advisor.get('total_aum') or 0):,.2f}",
        f"Total Clients: {advisor.get('total_clients', 0)}",
        f"Total Revenue: Rs.{(advisor.get('total_revenue') or 0):,.2f}",
        f"Total Commission: Rs.{(advisor.get('total_commission') or 0):,.2f}",
        f"Active SIPs: {advisor.get('active_sip_count', 0)}",
    ]
    return "\n".join(lines)


def get_advisor_with_highest_revenue() -> Optional[str]:
    advisors = fetch_mart("advisor")
    if not advisors:
        return None
    sorted_advisors = sorted(advisors, key=lambda x: float(x.get("total_revenue", 0) or 0), reverse=True)
    top_advisor = sorted_advisors[0]
    lines = [
        "TOP REVENUE ADVISOR", "=" * 60,
        f"Advisor: {top_advisor.get('advisor_name')}",
        f"Total Revenue: Rs.{(top_advisor.get('total_revenue') or 0):,.2f}",
        f"Total Clients: {top_advisor.get('total_clients', 0)}",
        f"Total AUM: Rs.{(top_advisor.get('total_aum') or 0):,.2f}",
        f"Total Commission: Rs.{(top_advisor.get('total_commission') or 0):,.2f}",
        f"Active SIPs: {top_advisor.get('active_sip_count', 0)}",
    ]
    return "\n".join(lines)


def compare_amcs(amc1: str, amc2: str) -> Optional[str]:
    amcs = fetch_mart("amc")
    if not amcs:
        return None
    a1 = next((a for a in amcs if amc1.lower() in a.get("amc_name", "").lower()), None)
    a2 = next((a for a in amcs if amc2.lower() in a.get("amc_name", "").lower()), None)
    if not a1 or not a2:
        return f"Could not find both AMCs: {amc1} and {amc2}"
    lines = [
        f"AMC COMPARISON: {a1.get('amc_name')} vs {a2.get('amc_name')}", "=" * 70,
        f"{'Metric':<30} {a1.get('amc_name')[:20]:<20} {a2.get('amc_name')[:20]:<20}",
        "-" * 70,
        f"{'Total AUM':<30} Rs.{(a1.get('total_aum') or 0):,.0f}   Rs.{(a2.get('total_aum') or 0):,.0f}",
        f"{'Investor Count':<30} {a1.get('investor_count', 0):<20} {a2.get('investor_count', 0):<20}",
        f"{'Scheme Count':<30} {a1.get('scheme_count', 0):<20} {a2.get('scheme_count', 0):<20}",
        f"{'Average Return':<30} {(a1.get('average_return') or 0):.2f}%   {(a2.get('average_return') or 0):.2f}%",
    ]
    return "\n".join(lines)


def answer_analytical(question: str) -> Tuple[Optional[str], Dict]:
    q = question.lower()

    # CLIENT BY ID - checked FIRST and unconditionally whenever a client id
    # is named, so a specific-client question is never mistaken for a
    # mart-wide aggregate question further down.
    client_id_match = re.search(r'client\s*(?:id\s*)?(\d+)', q)
    if client_id_match and "top" not in q and "compare" not in q:
        client_id = int(client_id_match.group(1))
        return answer_client_query(client_id, question)

    if "advisor" in q and "highest" in q and ("gain" in q or "profit" in q) and ("client" in q or "portfolio" in q):
        result = find_advisor_for_best_client()
        if result:
            return result, {"type": "complex", "query": "advisor_for_best_client"}

    if "advisor" in q and "highest" in q and "revenue" in q and ("clients" in q or "manage" in q):
        result = get_advisor_with_highest_revenue()
        if result:
            return result, {"type": "complex", "query": "advisor_highest_revenue"}

    if "compare" in q and "amc" in q:
        amc_names = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*AMC', question, re.IGNORECASE)
        if len(amc_names) >= 2:
            result = compare_amcs(amc_names[0], amc_names[1])
            if result:
                return result, {"type": "complex", "query": "compare_amcs"}

    if "compare" in q or "comparison" in q:
        names = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', question)
        if len(names) >= 2:
            name1, name2 = names[0], names[1]
            mart = detect_mart(q)
            if mart == "advisor" or "advisor" in q:
                a1, a2 = get_advisor_details(name1), get_advisor_details(name2)
                if a1 and a2:
                    lines = [
                        f"ADVISOR COMPARISON: {name1} vs {name2}", "=" * 70,
                        f"{'Metric':<30} {name1:<20} {name2:<20}", "-" * 70,
                        f"{'Total AUM':<30} Rs.{(a1.get('total_aum') or 0):,.0f}   Rs.{(a2.get('total_aum') or 0):,.0f}",
                        f"{'Total Revenue':<30} Rs.{(a1.get('total_revenue') or 0):,.0f}   Rs.{(a2.get('total_revenue') or 0):,.0f}",
                        f"{'Total Clients':<30} {a1.get('total_clients', 0):<20} {a2.get('total_clients', 0):<20}",
                        f"{'Commission':<30} Rs.{(a1.get('total_commission') or 0):,.0f}   Rs.{(a2.get('total_commission') or 0):,.0f}",
                        f"{'Active SIPs':<30} {a1.get('active_sip_count', 0):<20} {a2.get('active_sip_count', 0):<20}",
                    ]
                    return "\n".join(lines), {"mart": "advisor", "comparison": True}
            elif mart == "scheme" or "scheme" in q:
                s1, s2 = get_scheme_details(name1), get_scheme_details(name2)
                if s1 and s2:
                    lines = [
                        f"SCHEME COMPARISON: {name1} vs {name2}", "=" * 70,
                        f"{'Metric':<30} {name1:<20} {name2:<20}", "-" * 70,
                        f"{'Total AUM':<30} Rs.{(s1.get('total_aum') or 0):,.0f}   Rs.{(s2.get('total_aum') or 0):,.0f}",
                        f"{'Average Return':<30} {(s1.get('average_return') or 0):.2f}%   {(s2.get('average_return') or 0):.2f}%",
                        f"{'Investors':<30} {s1.get('investor_count', 0):<20} {s2.get('investor_count', 0):<20}",
                        f"{'Latest NAV':<30} {(s1.get('latest_nav') or 0):.2f}   {(s2.get('latest_nav') or 0):.2f}",
                    ]
                    return "\n".join(lines), {"mart": "scheme", "comparison": True}

    if any(word in q for word in ["executive summary", "management report", "overall business", "business health"]):
        exec_data = fetch_mart("executive")
        if exec_data:
            e = exec_data[0]
            lines = [
                "EXECUTIVE SUMMARY", "=" * 60,
                f"Total Clients: {e.get('total_clients', 0):,}",
                f"Active Advisors: {e.get('total_advisors', 0):,}",
                f"Total AUM: Rs.{(e.get('total_aum') or 0):,.2f}",
                f"Total Investment: Rs.{(e.get('total_investment') or 0):,.2f}",
                f"Total Redemption: Rs.{(e.get('total_redemption') or 0):,.2f}",
                f"Total Revenue: Rs.{(e.get('total_revenue') or 0):,.2f}",
                f"Active SIPs: {e.get('active_sips', 0):,}",
                f"Active Schemes: {e.get('active_schemes', 0):,}",
                f"Dashboard Date: {e.get('dashboard_date', 'N/A')}",
            ]
            return "\n".join(lines), {"mart": "executive"}

    if "how many" in q or "count" in q:
        mart = detect_mart(q)
        if mart and mart in MART_ENDPOINTS:
            rows = fetch_mart(mart)
            if mart == "advisor":
                unique = len(set(r.get("advisor_name") for r in rows if r.get("advisor_name")))
                return f"Total active advisors: {unique}", {"mart": mart, "count": unique}
            elif mart == "client":
                unique = len(set(r.get("client_name") for r in rows if r.get("client_name")))
                return f"Total clients: {unique}", {"mart": mart, "count": unique}
            elif mart == "scheme":
                unique = len(set(r.get("scheme_name") for r in rows if r.get("scheme_name")))
                return f"Total schemes: {unique}", {"mart": mart, "count": unique}
            elif mart == "sip":
                return f"Total SIP records: {len(rows)}", {"mart": mart, "count": len(rows)}
            elif mart == "amc":
                unique = len(set(r.get("amc_name") for r in rows if r.get("amc_name")))
                return f"Total AMCs: {unique}", {"mart": mart, "count": unique}

    threshold_match = re.search(r'(?:more than|greater than|above|below|less than)\s*(\d+)', q)
    if threshold_match:
        threshold = float(threshold_match.group(1))
        if "client" in q and "scheme" in q and ("active" in q or "schemes" in q):
            clients = fetch_mart("client")
            filtered = filter_by_threshold(clients, "active_scheme_count", threshold, "gt")
            if filtered:
                lines = [f"Clients with more than {threshold} active schemes:", "=" * 50]
                for c in filtered:
                    lines.append(f"  - {c.get('client_name')}: {c.get('active_scheme_count', 0)} schemes")
                return "\n".join(lines), {"mart": "client", "filtered": len(filtered)}
        if "gain" in q:
            clients = fetch_mart("client")
            filtered = filter_by_threshold(clients, "gain_percent", threshold, "gt" if "above" in q or "greater" in q else "lt")
            if filtered:
                lines = [f"Clients with gain {'above' if 'above' in q else 'below'} {threshold}%:", "=" * 50]
                for c in filtered[:20]:
                    lines.append(f"  - {c.get('client_name')}: {(c.get('gain_percent') or 0):.1f}%")
                return "\n".join(lines), {"mart": "client", "filtered": len(filtered)}

    if ("advisor" in q or "adviser" in q) and any(w in q for w in ["success", "profit", "ratio", "performance", "gain"]):
        advisor_rows, client_rows = fetch_mart("advisor"), fetch_mart("client")
        if not advisor_rows or not client_rows:
            return None, {"reason": "No data available"}
        results = calculate_advisor_client_profit(advisor_rows, client_rows)
        if not results:
            return None, {"reason": "No advisor-client data found"}
        if "profit" in q or "gain" in q:
            sorted_advisors = sorted(results.items(), key=lambda x: x[1]["total_profit"], reverse=True)
            metric_label = "TOTAL PROFIT GENERATED"
        elif "success" in q or "ratio" in q:
            sorted_advisors = sorted(results.items(), key=lambda x: x[1]["success_ratio"], reverse=True)
            metric_label = "CLIENT SUCCESS RATIO"
        else:
            sorted_advisors = sorted(results.items(), key=lambda x: x[1]["total_clients"], reverse=True)
            metric_label = "TOTAL CLIENTS"
        top_n = detect_top_n(q)
        top_advisors = sorted_advisors[:top_n]
        lines = [f"TOP {len(top_advisors)} ADVISORS BY {metric_label}", "=" * 80,
                 f"{'#':<4} {'Advisor Name':<25} {'Profit (Rs.)':<18} {'Success %':<12} {'Clients':<10} {'AUM (Rs.)':<15}",
                 "-" * 80]
        for i, (name, data) in enumerate(top_advisors, 1):
            lines.append(
                f"{i:<4} {name[:24]:<25} {data['total_profit']:>14,.2f}  "
                f"{data['success_ratio']:>6.1f}%{'':<5} {data['total_clients']:<10} {data['total_aum']:>14,.0f}"
            )
        lines.append("-" * 80)
        return "\n".join(lines), {"mart": "advisor", "metric": metric_label, "top_n": top_n}

    mart = detect_mart(q)
    if mart is None:
        return None, {"reason": f"No mart detected for: {question[:50]}"}
    if mart not in MART_ENDPOINTS or mart not in NAME_FIELD:
        return None, {"reason": f"Mart '{mart}' not supported"}

    metric = detect_metric(q, mart)
    if metric is None:
        return None, {"reason": f"No metric detected for mart '{mart}'"}

    name_field = NAME_FIELD[mart]
    top_n = detect_top_n(q)
    order = detect_order(q)
    if metric == "gain_loss" and "loss" in q and "gain" not in q:
        order = "asc"  # biggest loss = most negative gain_loss, so ascending puts it first

    rows = fetch_mart(mart)
    if not rows:
        return None, {"reason": f"No data in mart '{mart}'"}

    if ("total" in q or "sum" in q) and "top" not in q:
        totals = aggregate(rows, name_field, metric)
        grand_total = sum(totals.values())
        return f"The total {metric.replace('_', ' ')} across all {mart}s is Rs.{grand_total:,.2f}", \
            {"mart": mart, "metric": metric, "rows_fetched": len(rows)}

    if ("average" in q or "avg" in q) and not any(w in q for w in ["highest", "lowest", "best", "worst", "top", "most", "least"]):
        totals = aggregate(rows, name_field, metric)
        avg = sum(totals.values()) / len(totals) if totals else 0
        return f"The average {metric.replace('_', ' ')} across {len(totals)} {mart}s is {avg:,.2f}", \
            {"mart": mart, "metric": metric, "rows_fetched": len(rows)}

    totals = aggregate(rows, name_field, metric)
    if not totals:
        return None, {"reason": f"No data for metric '{metric}'"}

    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=(order == "desc"))[:top_n]
    lines = [f"Top {len(ranked)} {mart}s by {metric.replace('_', ' ')} ({'descending' if order == 'desc' else 'ascending'}):", "-" * 40]
    for i, (name, value) in enumerate(ranked, 1):
        lines.append(f"{i}. {name}: {value:,.2f}")

    debug = {
        "mart": mart, "metric": metric, "name_field": name_field,
        "rows_fetched": len(rows), "unique_entities": len(totals),
        "top_n": top_n, "order": order,
    }
    return "\n".join(lines), debug