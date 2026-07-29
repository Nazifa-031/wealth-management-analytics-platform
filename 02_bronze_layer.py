# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Bronze Layer
# MAGIC Ingests every `raw.*` table as-is into `bronze.*`, adding standard ingestion
# MAGIC metadata columns. No business logic or cleaning happens here — bronze is a
# MAGIC faithful, auditable copy of the source extract.

# COMMAND ----------

from pyspark.sql import functions as F

RAW_TABLES = [
    "regions", "branches", "advisors", "clients", "client_addresses", "nominees",
    "risk_profiles", "amcs", "scheme_categories", "fund_managers", "schemes", "folios",
    "transactions", "sip_registrations", "sip_installments", "switch_transactions",
    "redemption_transactions", "nav_history", "benchmark_returns", "brokerage",
    "trail_commissions", "goals", "goal_investments", "portfolio_snapshots",
]

# Maps each table to the source system it came from (for lineage/audit columns)
SOURCE_SYSTEM = {
    "regions": "advisor_management", "branches": "advisor_management", "advisors": "advisor_management",
    "clients": "client_management", "client_addresses": "client_management", "nominees": "client_management",
    "risk_profiles": "client_management",
    "amcs": "amc_management",
    "scheme_categories": "scheme_management", "fund_managers": "scheme_management", "schemes": "scheme_management",
    "folios": "transaction_management", "transactions": "transaction_management",
    "switch_transactions": "transaction_management", "redemption_transactions": "transaction_management",
    "sip_registrations": "sip_management", "sip_installments": "sip_management",
    "nav_history": "revenue_management", "benchmark_returns": "revenue_management",
    "brokerage": "revenue_management", "trail_commissions": "revenue_management",
    "goals": "goal_planning", "goal_investments": "goal_planning",
    "portfolio_snapshots": "portfolio_management",
}

# COMMAND ----------

for name in RAW_TABLES:
    df = spark.table(f"raw.{name}")
    df = (
        df.withColumn("_ingested_at", F.current_timestamp())
          .withColumn("_source_system", F.lit(SOURCE_SYSTEM[name]))
    )
    df.write.mode("overwrite").saveAsTable(f"bronze.{name}")
    print(f"bronze.{name:28s} -> {df.count():6d} rows")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT table_name FROM information_schema.tables WHERE table_schema = 'bronze' ORDER BY table_name;

# COMMAND ----------

# MAGIC %md Next: run `03_silver_layer` to clean and standardize these tables.
