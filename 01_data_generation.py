# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Raw Data Generation
# MAGIC Generates synthetic data for all 9 source systems (24 tables) of the Wealth
# MAGIC Management Analytics Platform, and writes each as a managed Delta table in the
# MAGIC `raw` schema.
# MAGIC
# MAGIC Source systems covered: Client Management, Advisor Management, AMC Management,
# MAGIC Scheme Management, Transaction Management, SIP Management, Revenue Management,
# MAGIC Goal Planning, Portfolio Management.

# COMMAND ----------

# MAGIC %pip install faker
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

import random
from datetime import date, timedelta
import pandas as pd
from faker import Faker

fake = Faker("en_IN")
Faker.seed(42)
random.seed(42)

# ---------------- Volumes (tune these up/down as needed) ----------------
N_REGIONS = 5
N_BRANCHES = 20
N_ADVISORS = 100
N_CLIENTS = 1000
N_AMCS = 10
N_CATEGORIES = 6
N_SCHEMES = 100
N_FUND_MANAGERS = 30
N_FOLIOS = 1500
N_TRANSACTIONS = 8000
N_SIP_REG = 500
N_SWITCH = 300
N_REDEMPTIONS = 1500
N_GOALS = 800
NAV_DAYS = 180

START_DATE = date(2023, 1, 1)
END_DATE = date(2026, 6, 30)


def random_date(start=START_DATE, end=END_DATE):
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

# COMMAND ----------

# MAGIC %md ### Client Management: regions, branches, advisors, clients, addresses, nominees, risk_profiles

# COMMAND ----------

region_names = ["North", "South", "East", "West", "Central"][:N_REGIONS]
df_regions = pd.DataFrame({
    "region_id": range(1, N_REGIONS + 1),
    "region_name": region_names,
})

cities = [fake.city() for _ in range(N_BRANCHES)]
df_branches = pd.DataFrame({
    "branch_id": range(1, N_BRANCHES + 1),
    "branch_name": [f"{c} Branch" for c in cities],
    "city": cities,
    "region_id": [random.randint(1, N_REGIONS) for _ in range(N_BRANCHES)],
})

df_advisors = pd.DataFrame({
    "advisor_id": range(1, N_ADVISORS + 1),
    "advisor_name": [fake.name() for _ in range(N_ADVISORS)],
    "branch_id": [random.randint(1, N_BRANCHES) for _ in range(N_ADVISORS)],
    "joining_date": [random_date(date(2015, 1, 1), date(2025, 12, 31)) for _ in range(N_ADVISORS)],
    "status": [random.choices(["ACTIVE", "INACTIVE"], weights=[92, 8])[0] for _ in range(N_ADVISORS)],
})

df_clients = pd.DataFrame({
    "client_id": range(1, N_CLIENTS + 1),
    "client_name": [fake.name() for _ in range(N_CLIENTS)],
    "dob": [fake.date_of_birth(minimum_age=21, maximum_age=75) for _ in range(N_CLIENTS)],
    "pan": [fake.bothify(text="?????####?").upper() for _ in range(N_CLIENTS)],
    "mobile": [fake.msisdn()[:10] for _ in range(N_CLIENTS)],
    "email": [fake.email() for _ in range(N_CLIENTS)],
    "advisor_id": [random.randint(1, N_ADVISORS) for _ in range(N_CLIENTS)],
    "onboarding_date": [random_date(date(2018, 1, 1), END_DATE) for _ in range(N_CLIENTS)],
})

df_client_addresses = pd.DataFrame({
    "address_id": range(1, N_CLIENTS + 1),
    "client_id": df_clients["client_id"],
    "address_line": [fake.street_address() for _ in range(N_CLIENTS)],
    "city": [fake.city() for _ in range(N_CLIENTS)],
    "state": [fake.state() for _ in range(N_CLIENTS)],
    "pincode": [fake.postcode() for _ in range(N_CLIENTS)],
})

n_nominees = int(N_CLIENTS * 1.2)
df_nominees = pd.DataFrame({
    "nominee_id": range(1, n_nominees + 1),
    "client_id": [random.randint(1, N_CLIENTS) for _ in range(n_nominees)],
    "nominee_name": [fake.name() for _ in range(n_nominees)],
    "relationship": [random.choice(["Spouse", "Child", "Parent", "Sibling"]) for _ in range(n_nominees)],
})

risk_categories = ["Conservative", "Moderate", "Aggressive"]
df_risk_profiles = pd.DataFrame({
    "risk_profile_id": range(1, N_CLIENTS + 1),
    "client_id": df_clients["client_id"],
    "risk_category": [random.choice(risk_categories) for _ in range(N_CLIENTS)],
    "risk_score": [random.randint(1, 100) for _ in range(N_CLIENTS)],
})

# COMMAND ----------

# MAGIC %md ### AMC & Scheme Management: amcs, scheme_categories, fund_managers, schemes

# COMMAND ----------

amc_names = [fake.company() + " Mutual Fund" for _ in range(N_AMCS)]
df_amcs = pd.DataFrame({"amc_id": range(1, N_AMCS + 1), "amc_name": amc_names})

cat_names = ["Equity", "Debt", "Hybrid", "Liquid", "ELSS", "Index"][:N_CATEGORIES]
df_scheme_categories = pd.DataFrame({
    "category_id": range(1, N_CATEGORIES + 1),
    "category_name": cat_names,
})

df_fund_managers = pd.DataFrame({
    "fund_manager_id": range(1, N_FUND_MANAGERS + 1),
    "fund_manager_name": [fake.name() for _ in range(N_FUND_MANAGERS)],
})

asset_class_map = {"Equity": "Equity", "Debt": "Debt", "Hybrid": "Hybrid",
                    "Liquid": "Debt", "ELSS": "Equity", "Index": "Equity"}
df_schemes = pd.DataFrame({
    "scheme_id": range(1, N_SCHEMES + 1),
    "scheme_name": [f"{random.choice(amc_names).split(' Mutual')[0]} {random.choice(cat_names)} Fund {i}"
                     for i in range(N_SCHEMES)],
    "amc_id": [random.randint(1, N_AMCS) for _ in range(N_SCHEMES)],
    "category_id": [random.randint(1, N_CATEGORIES) for _ in range(N_SCHEMES)],
    "fund_manager_id": [random.randint(1, N_FUND_MANAGERS) for _ in range(N_SCHEMES)],
    "risk_level": [random.choice(risk_categories) for _ in range(N_SCHEMES)],
    "expense_ratio": [round(random.uniform(0.5, 2.5), 2) for _ in range(N_SCHEMES)],
})
df_schemes["asset_class"] = df_schemes["category_id"].map(
    dict(zip(df_scheme_categories["category_id"], df_scheme_categories["category_name"].map(asset_class_map)))
)

# COMMAND ----------

# MAGIC %md ### Transaction & SIP Management: folios, transactions, sip_registrations, sip_installments, switch_transactions, redemption_transactions

# COMMAND ----------

df_folios = pd.DataFrame({
    "folio_id": range(1, N_FOLIOS + 1),
    "client_id": [random.randint(1, N_CLIENTS) for _ in range(N_FOLIOS)],
    "amc_id": [random.randint(1, N_AMCS) for _ in range(N_FOLIOS)],
    "opened_date": [random_date(date(2018, 1, 1), END_DATE) for _ in range(N_FOLIOS)],
})

txn_types = ["PURCHASE", "ADDITIONAL_PURCHASE"]
transactions = []
for i in range(1, N_TRANSACTIONS + 1):
    amount = round(random.uniform(1000, 500000), 2)
    nav = round(random.uniform(10, 500), 4)
    transactions.append({
        "transaction_id": i,
        "folio_id": random.randint(1, N_FOLIOS),
        "scheme_id": random.randint(1, N_SCHEMES),
        "transaction_date": random_date(),
        "transaction_type": random.choice(txn_types),
        "amount": amount,
        "units": round(amount / nav, 4),
        "nav": nav,
    })
df_transactions = pd.DataFrame(transactions)

df_sip_registrations = pd.DataFrame({
    "sip_id": range(1, N_SIP_REG + 1),
    "folio_id": [random.randint(1, N_FOLIOS) for _ in range(N_SIP_REG)],
    "scheme_id": [random.randint(1, N_SCHEMES) for _ in range(N_SIP_REG)],
    "sip_amount": [round(random.choice([500, 1000, 2000, 5000, 10000]), 2) for _ in range(N_SIP_REG)],
    "start_date": [random_date(date(2020, 1, 1), END_DATE) for _ in range(N_SIP_REG)],
    "frequency": ["MONTHLY"] * N_SIP_REG,
    "status": [random.choices(["ACTIVE", "STOPPED"], weights=[80, 20])[0] for _ in range(N_SIP_REG)],
})

installments = []
inst_id = 1
for _, sip in df_sip_registrations.iterrows():
    n_inst = random.randint(3, 24)
    for k in range(n_inst):
        inst_date = sip["start_date"] + timedelta(days=30 * k)
        if inst_date > END_DATE:
            break
        nav = round(random.uniform(10, 500), 4)
        installments.append({
            "sip_installment_id": inst_id,
            "sip_id": sip["sip_id"],
            "installment_date": inst_date,
            "installment_amount": sip["sip_amount"],
            "units": round(sip["sip_amount"] / nav, 4),
            "nav": nav,
        })
        inst_id += 1
df_sip_installments = pd.DataFrame(installments)

df_switch_transactions = pd.DataFrame({
    "switch_id": range(1, N_SWITCH + 1),
    "folio_id": [random.randint(1, N_FOLIOS) for _ in range(N_SWITCH)],
    "from_scheme_id": [random.randint(1, N_SCHEMES) for _ in range(N_SWITCH)],
    "to_scheme_id": [random.randint(1, N_SCHEMES) for _ in range(N_SWITCH)],
    "switch_date": [random_date() for _ in range(N_SWITCH)],
    "amount": [round(random.uniform(1000, 100000), 2) for _ in range(N_SWITCH)],
})

redemptions = []
for i in range(1, N_REDEMPTIONS + 1):
    nav = round(random.uniform(10, 500), 4)
    units = round(random.uniform(10, 5000), 4)
    redemptions.append({
        "redemption_id": i,
        "folio_id": random.randint(1, N_FOLIOS),
        "scheme_id": random.randint(1, N_SCHEMES),
        "redemption_date": random_date(),
        "redeemed_units": units,
        "nav": nav,
        "redeemed_amount": round(units * nav, 2),
    })
df_redemption_transactions = pd.DataFrame(redemptions)

# COMMAND ----------

# MAGIC %md ### Revenue Management: nav_history, benchmark_returns, brokerage, trail_commissions

# COMMAND ----------

nav_rows = []
nav_start = END_DATE - timedelta(days=NAV_DAYS)
for scheme_id in range(1, N_SCHEMES + 1):
    base_nav = round(random.uniform(10, 500), 2)
    for d in range(NAV_DAYS):
        this_date = nav_start + timedelta(days=d)
        base_nav = round(base_nav * (1 + random.uniform(-0.01, 0.012)), 4)
        nav_rows.append({"scheme_id": scheme_id, "nav_date": this_date, "nav": base_nav})
df_nav_history = pd.DataFrame(nav_rows)

benchmarks = ["NIFTY50", "SENSEX", "NIFTY_MIDCAP150", "CRISIL_DEBT_INDEX"]
bench_rows = []
for b in benchmarks:
    base = 100.0
    for d in range(NAV_DAYS):
        this_date = nav_start + timedelta(days=d)
        base = round(base * (1 + random.uniform(-0.008, 0.01)), 4)
        bench_rows.append({"benchmark_name": b, "return_date": this_date, "index_value": base})
df_benchmark_returns = pd.DataFrame(bench_rows)

brokerage_rows = []
for i, t in df_transactions.iterrows():
    brokerage_rows.append({
        "brokerage_id": i + 1,
        "transaction_id": t["transaction_id"],
        "advisor_id": random.randint(1, N_ADVISORS),
        "scheme_id": t["scheme_id"],
        "commission_date": t["transaction_date"],
        "commission_amount": round(t["amount"] * random.uniform(0.005, 0.02), 2),
    })
df_brokerage = pd.DataFrame(brokerage_rows)

n_trail = 3000
df_trail_commissions = pd.DataFrame({
    "trail_commission_id": range(1, n_trail + 1),
    "advisor_id": [random.randint(1, N_ADVISORS) for _ in range(n_trail)],
    "scheme_id": [random.randint(1, N_SCHEMES) for _ in range(n_trail)],
    "commission_month": [random_date(date(2024, 1, 1), END_DATE).replace(day=1) for _ in range(n_trail)],
    "commission_amount": [round(random.uniform(50, 5000), 2) for _ in range(n_trail)],
})

# COMMAND ----------

# MAGIC %md ### Goal Planning & Portfolio Management: goals, goal_investments, portfolio_snapshots

# COMMAND ----------

goal_types = ["Retirement", "Child Education", "Home Purchase", "Vacation", "Wealth Creation", "Emergency Fund"]
df_goals = pd.DataFrame({
    "goal_id": range(1, N_GOALS + 1),
    "client_id": [random.randint(1, N_CLIENTS) for _ in range(N_GOALS)],
    "goal_name": [random.choice(goal_types) for _ in range(N_GOALS)],
    "target_amount": [round(random.uniform(100000, 10000000), 2) for _ in range(N_GOALS)],
    "target_date": [random_date(date(2027, 1, 1), date(2045, 12, 31)) for _ in range(N_GOALS)],
})

n_goal_inv = int(N_GOALS * 1.5)
df_goal_investments = pd.DataFrame({
    "goal_investment_id": range(1, n_goal_inv + 1),
    "goal_id": [random.randint(1, N_GOALS) for _ in range(n_goal_inv)],
    "folio_id": [random.randint(1, N_FOLIOS) for _ in range(n_goal_inv)],
    "allocated_amount": [round(random.uniform(5000, 500000), 2) for _ in range(n_goal_inv)],
})

snap_rows = []
snap_id = 1
for client_id in range(1, N_CLIENTS + 1, 2):  # every other client, to keep volume sane
    for month_offset in range(6):
        snap_date = END_DATE.replace(day=1) - timedelta(days=30 * month_offset)
        snap_rows.append({
            "snapshot_id": snap_id,
            "client_id": client_id,
            "snapshot_date": snap_date,
            "total_market_value": round(random.uniform(10000, 5000000), 2),
            "total_cost_value": round(random.uniform(10000, 5000000), 2),
        })
        snap_id += 1
df_portfolio_snapshots = pd.DataFrame(snap_rows)

# COMMAND ----------

# MAGIC %md ### Write everything to the `raw` schema as managed Delta tables

# COMMAND ----------

tables = {
    "regions": df_regions, "branches": df_branches, "advisors": df_advisors,
    "clients": df_clients, "client_addresses": df_client_addresses, "nominees": df_nominees,
    "risk_profiles": df_risk_profiles, "amcs": df_amcs, "scheme_categories": df_scheme_categories,
    "fund_managers": df_fund_managers, "schemes": df_schemes, "folios": df_folios,
    "transactions": df_transactions, "sip_registrations": df_sip_registrations,
    "sip_installments": df_sip_installments, "switch_transactions": df_switch_transactions,
    "redemption_transactions": df_redemption_transactions, "nav_history": df_nav_history,
    "benchmark_returns": df_benchmark_returns, "brokerage": df_brokerage,
    "trail_commissions": df_trail_commissions, "goals": df_goals,
    "goal_investments": df_goal_investments, "portfolio_snapshots": df_portfolio_snapshots,
}

for name, pdf in tables.items():
    sdf = spark.createDataFrame(pdf)
    sdf.write.mode("overwrite").saveAsTable(f"raw.{name}")
    print(f"raw.{name:28s} -> {sdf.count():6d} rows")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = 'raw' ORDER BY table_name;

# COMMAND ----------

# MAGIC %md
# MAGIC 24 tables generated across 9 source systems (Client, Advisor, AMC, Scheme,
# MAGIC Transaction, SIP, Revenue, Goal, Portfolio). Next: run `02_bronze_layer`.
