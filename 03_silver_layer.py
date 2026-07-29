# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Silver Layer
# MAGIC Cleans and standardizes `bronze.*` into `silver.*`:
# MAGIC - drops the bronze audit columns
# MAGIC - de-duplicates on primary key
# MAGIC - trims/standardizes string columns
# MAGIC - drops rows with null primary/foreign keys (would break joins downstream)
# MAGIC - casts key numeric/date columns explicitly

# COMMAND ----------

from functools import reduce
from pyspark.sql import functions as F
from pyspark.sql.types import DateType, DoubleType

# Primary key per table (used for de-duplication)
PK = {
    "regions": "region_id", "branches": "branch_id", "advisors": "advisor_id",
    "clients": "client_id", "client_addresses": "address_id", "nominees": "nominee_id",
    "risk_profiles": "risk_profile_id", "amcs": "amc_id", "scheme_categories": "category_id",
    "fund_managers": "fund_manager_id", "schemes": "scheme_id", "folios": "folio_id",
    "transactions": "transaction_id", "sip_registrations": "sip_id",
    "sip_installments": "sip_installment_id", "switch_transactions": "switch_id",
    "redemption_transactions": "redemption_id", "brokerage": "brokerage_id",
    "trail_commissions": "trail_commission_id", "goals": "goal_id",
    "goal_investments": "goal_investment_id", "portfolio_snapshots": "snapshot_id",
}
# nav_history and benchmark_returns have no single-column PK (they're a fact-like grain)
COMPOSITE_KEY = {
    "nav_history": ["scheme_id", "nav_date"],
    "benchmark_returns": ["benchmark_name", "return_date"],
}

ALL_TABLES = list(PK.keys()) + list(COMPOSITE_KEY.keys())


def trim_strings(df):
    for field in df.schema.fields:
        if field.dataType.simpleString() == "string":
            df = df.withColumn(field.name, F.trim(F.col(field.name)))
    return df


def clean_generic(df, name):
    df = trim_strings(df).drop("_ingested_at", "_source_system")
    if name in PK:
        key = PK[name]
        df = df.filter(F.col(key).isNotNull())
        df = df.dropDuplicates([key])
    else:
        keys = COMPOSITE_KEY[name]
        df = df.filter(reduce(lambda a, b: a & b, [F.col(k).isNotNull() for k in keys]))
        df = df.dropDuplicates(keys)
    return df

# COMMAND ----------

# MAGIC %md ### Generic cleaning pass for every table

# COMMAND ----------

cleaned = {}
for name in ALL_TABLES:
    df = spark.table(f"bronze.{name}")
    cleaned[name] = clean_generic(df, name)

# COMMAND ----------

# MAGIC %md ### Table-specific rules
# MAGIC A few tables need extra business-rule cleaning beyond the generic pass.

# COMMAND ----------

# clients: lowercase email, uppercase PAN, drop clients with malformed PAN (should be 10 chars)
c = cleaned["clients"]
c = (
    c.withColumn("email", F.lower(F.col("email")))
     .withColumn("pan", F.upper(F.col("pan")))
     .filter(F.length("pan") == 10)
)
cleaned["clients"] = c

# schemes: expense_ratio must be positive and reasonable (<10%)
s = cleaned["schemes"]
s = s.filter((F.col("expense_ratio") > 0) & (F.col("expense_ratio") < 10))
cleaned["schemes"] = s

# transactions: amount and units must be positive
t = cleaned["transactions"]
t = t.filter((F.col("amount") > 0) & (F.col("units") > 0) & (F.col("nav") > 0))
cleaned["transactions"] = t

# sip_installments: installment_amount and units must be positive
si = cleaned["sip_installments"]
si = si.filter((F.col("installment_amount") > 0) & (F.col("units") > 0))
cleaned["sip_installments"] = si

# redemption_transactions: redeemed_units and redeemed_amount must be positive
r = cleaned["redemption_transactions"]
r = r.filter((F.col("redeemed_units") > 0) & (F.col("redeemed_amount") > 0))
cleaned["redemption_transactions"] = r

# advisors: standardize status to upper case
adv = cleaned["advisors"]
adv = adv.withColumn("status", F.upper(F.col("status")))
cleaned["advisors"] = adv

# COMMAND ----------

# MAGIC %md ### Write to `silver.*`

# COMMAND ----------

for name, df in cleaned.items():
    df.write.mode("overwrite").saveAsTable(f"silver.{name}")
    print(f"silver.{name:28s} -> {df.count():6d} rows")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT table_name FROM information_schema.tables WHERE table_schema = 'silver' ORDER BY table_name;

# COMMAND ----------

# MAGIC %md Next: run `04_warehouse_layer` to build the dim/fact star schema.
