# Databricks notebook source
# MAGIC %md
# MAGIC # 06 — Phase 3: Data Marts
# MAGIC Builds 8 business-facing data marts on top of `warehouse.*`, written to a new
# MAGIC `mart` schema. Each mart is a denormalized, pre-aggregated table designed to be
# MAGIC queried directly by dashboard — no joins required 

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS mart;

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

dim_client = spark.table("warehouse.dim_client")
dim_advisor = spark.table("warehouse.dim_advisor")
dim_amc = spark.table("warehouse.dim_amc")
dim_scheme = spark.table("warehouse.dim_scheme")
dim_time = spark.table("warehouse.dim_time")
fact_transactions = spark.table("warehouse.fact_transactions")
fact_sip_installments = spark.table("warehouse.fact_sip_installments")
fact_redemptions = spark.table("warehouse.fact_redemptions")
fact_commissions = spark.table("warehouse.fact_commissions")
fact_portfolio_aum = spark.table("warehouse.fact_portfolio_aum")

# "Latest" snapshot date_key in the AUM fact — most marts report as-of this date
latest_date_key = fact_portfolio_aum.agg(F.max("date_key")).first()[0]
latest_aum = fact_portfolio_aum.filter(F.col("date_key") == latest_date_key)
print(f"Using latest_date_key = {latest_date_key} for as-of-date marts")

# COMMAND ----------

# MAGIC %md ## 1. Client Portfolio Summary Mart
# MAGIC Grain: one row per client, as of the latest AUM snapshot date.

# COMMAND ----------

client_portfolio_summary = (
    latest_aum.alias("f")
    .groupBy("client_key", "advisor_key")
    .agg(
        F.sum("cost_value").alias("total_investment"),
        F.sum("market_value").alias("current_value"),
        F.sum("units_held").alias("total_units"),
        F.countDistinct(F.when(F.col("units_held") > 0, F.col("scheme_key"))).alias("active_scheme_count"),
    )
    .withColumn("gain_loss", F.col("current_value") - F.col("total_investment"))
    .withColumn(
        "gain_percent",
        F.when(F.col("total_investment") > 0, F.round(F.col("gain_loss") / F.col("total_investment") * 100, 2))
         .otherwise(F.lit(0.0)),
    )
    .join(dim_client.select("client_key", "client_id", "client_name"), "client_key", "left")
    .join(dim_advisor.select("advisor_key", "advisor_name"), "advisor_key", "left")
    .join(dim_time.filter(F.col("date_key") == latest_date_key).select("full_date"), how="cross")
    .select(
        "client_id", "client_name", "advisor_name",
        "total_investment", "current_value", "gain_loss", "gain_percent",
        "active_scheme_count", "total_units",
        F.col("full_date").alias("last_updated_date"),
    )
)
client_portfolio_summary.write.mode("overwrite").saveAsTable("mart.client_portfolio_summary")
print(f"mart.client_portfolio_summary -> {client_portfolio_summary.count()} rows")

# COMMAND ----------

# MAGIC %md ## 2. Advisor Performance Mart
# MAGIC Grain: one row per advisor.

# COMMAND ----------

# active SIPs per advisor, using true SIP status from silver (fact table doesn't carry status)
sip_reg = spark.table("silver.sip_registrations").filter(F.col("status") == "ACTIVE")
folios = spark.table("silver.folios").select("folio_id", "client_id")
client_advisor_map = dim_client.select("client_id", "advisor_id")
advisor_key_map = dim_advisor.select("advisor_id", "advisor_key")

active_sip_by_advisor = (
    sip_reg.join(folios, "folio_id", "left")
    .join(client_advisor_map, "client_id", "left")
    .join(advisor_key_map, "advisor_id", "left")
    .groupBy("advisor_key")
    .agg(F.countDistinct("sip_id").alias("active_sip_count"))
)

aum_by_advisor = (
    latest_aum.groupBy("advisor_key")
    .agg(
        F.sum("market_value").alias("total_aum"),
        F.countDistinct("client_key").alias("total_clients"),
    )
)

commission_by_advisor = (
    fact_commissions.groupBy("advisor_key")
    .agg(F.sum("commission_amount").alias("total_commission"))
)

advisor_performance = (
    dim_advisor.select("advisor_key", "advisor_id", "advisor_name")
    .join(aum_by_advisor, "advisor_key", "left")
    .join(commission_by_advisor, "advisor_key", "left")
    .join(active_sip_by_advisor, "advisor_key", "left")
    .fillna({"total_aum": 0.0, "total_clients": 0, "total_commission": 0.0, "active_sip_count": 0})
    .withColumn("total_revenue", F.col("total_commission"))  # only revenue source modeled is commissions
    .withColumn(
        "average_client_aum",
        F.when(F.col("total_clients") > 0, F.round(F.col("total_aum") / F.col("total_clients"), 2))
         .otherwise(F.lit(0.0)),
    )
    .join(dim_time.filter(F.col("date_key") == latest_date_key).select("full_date"), how="cross")
    .select(
        "advisor_id", "advisor_name", "total_clients", "total_aum", "total_commission",
        "total_revenue", "average_client_aum", "active_sip_count",
        F.col("full_date").alias("last_updated_date"),
    )
)
advisor_performance.write.mode("overwrite").saveAsTable("mart.advisor_performance")
print(f"mart.advisor_performance -> {advisor_performance.count()} rows")

# COMMAND ----------

# MAGIC %md ## 3. Scheme Performance Mart
# MAGIC Grain: one row per scheme.

# COMMAND ----------

scheme_agg = (
    latest_aum.groupBy("scheme_key")
    .agg(
        F.countDistinct(F.when(F.col("units_held") > 0, F.col("client_key"))).alias("investor_count"),
        F.sum("market_value").alias("total_aum"),
        F.sum("cost_value").alias("total_cost"),
        F.sum("units_held").alias("units_held"),
        F.max("latest_nav").alias("latest_nav"),
    )
    .withColumn(
        "average_return",
        F.when(F.col("total_cost") > 0, F.round((F.col("total_aum") - F.col("total_cost")) / F.col("total_cost") * 100, 2))
         .otherwise(F.lit(0.0)),
    )
)

scheme_performance = (
    dim_scheme.select("scheme_key", "scheme_id", "scheme_name", "amc_name", "category_name")
    .join(scheme_agg, "scheme_key", "left")
    .fillna({"investor_count": 0, "total_aum": 0.0, "units_held": 0.0, "average_return": 0.0})
    .join(dim_time.filter(F.col("date_key") == latest_date_key).select("full_date"), how="cross")
    .select(
        "scheme_id", "scheme_name", "amc_name", "category_name",
        "investor_count", "total_aum", "average_return", "units_held", "latest_nav",
        F.col("full_date").alias("last_updated_date"),
    )
)
scheme_performance.write.mode("overwrite").saveAsTable("mart.scheme_performance")
print(f"mart.scheme_performance -> {scheme_performance.count()} rows")

# COMMAND ----------

# MAGIC %md ## 4. Revenue Mart
# MAGIC Grain: one row per advisor + month + year.

# COMMAND ----------

revenue_mart = (
    fact_commissions.alias("c")
    .join(dim_time.select("date_key", "month", "year"), "date_key", "left")
    .join(dim_advisor.select("advisor_key", "advisor_id", "advisor_name"), "advisor_key", "left")
    .groupBy("advisor_id", "advisor_name", "month", "year")
    .agg(
        F.sum(F.when(F.col("commission_type") == "BROKERAGE", F.col("commission_amount")).otherwise(0)).alias("brokerage_amount"),
        F.sum(F.when(F.col("commission_type") == "TRAIL", F.col("commission_amount")).otherwise(0)).alias("trail_commission"),
        F.sum("commission_amount").alias("total_revenue"),
    )
    .select("advisor_id", "advisor_name", "month", "year", "brokerage_amount", "trail_commission", "total_revenue")
)
revenue_mart.write.mode("overwrite").saveAsTable("mart.revenue")
print(f"mart.revenue -> {revenue_mart.count()} rows")

# COMMAND ----------

# MAGIC %md ## 5. SIP Analytics Mart
# MAGIC Grain: one row per client + scheme (all installments to date).

# COMMAND ----------

latest_nav_by_scheme = (
    latest_aum.groupBy("scheme_key").agg(F.max("latest_nav").alias("latest_nav"))
)

sip_analytics = (
    fact_sip_installments.groupBy("client_key", "scheme_key")
    .agg(
        F.count("*").alias("installment_count"),
        F.sum("installment_amount").alias("total_sip_amount"),
        F.sum("units").alias("total_units"),
    )
    .join(dim_client.select("client_key", "client_id", "client_name"), "client_key", "left")
    .join(dim_scheme.select("scheme_key", "scheme_name"), "scheme_key", "left")
    .join(latest_nav_by_scheme, "scheme_key", "left")
    .withColumn("current_value", F.round(F.col("total_units") * F.col("latest_nav"), 2))
    .select(
        "client_id", "client_name", "scheme_name",
        "installment_count", "total_sip_amount", "total_units", "latest_nav", "current_value",
    )
)
sip_analytics.write.mode("overwrite").saveAsTable("mart.sip_analytics")
print(f"mart.sip_analytics -> {sip_analytics.count()} rows")

# COMMAND ----------

# MAGIC %md ## 6. Redemption Analytics Mart
# MAGIC Grain: one row per client + scheme + redemption month/year.

# COMMAND ----------

redemption_analytics = (
    fact_redemptions.alias("r")
    .join(dim_time.select("date_key", F.col("month").alias("redemption_month"), F.col("year").alias("redemption_year")), "date_key", "left")
    .join(dim_client.select("client_key", "client_id", "client_name"), "client_key", "left")
    .join(dim_scheme.select("scheme_key", "scheme_name"), "scheme_key", "left")
    .groupBy("client_id", "client_name", "scheme_name", "redemption_month", "redemption_year")
    .agg(
        F.count("*").alias("redemption_count"),
        F.sum("redeemed_amount").alias("redeemed_amount"),
        F.sum("redeemed_units").alias("redeemed_units"),
    )
    .select(
        "client_id", "client_name", "scheme_name",
        "redemption_count", "redeemed_amount", "redeemed_units",
        "redemption_month", "redemption_year",
    )
)
redemption_analytics.write.mode("overwrite").saveAsTable("mart.redemption_analytics")
print(f"mart.redemption_analytics -> {redemption_analytics.count()} rows")

# COMMAND ----------

# MAGIC %md ## 7. AMC Business Mart
# MAGIC Grain: one row per AMC.

# COMMAND ----------

amc_scheme_stats = (
    latest_aum.alias("f")
    .join(dim_scheme.select("scheme_key", "amc_id"), "scheme_key", "left")
    .groupBy("amc_id")
    .agg(
        F.sum("market_value").alias("total_aum"),
        F.sum("cost_value").alias("total_cost"),
        F.countDistinct(F.when(F.col("units_held") > 0, F.col("client_key"))).alias("investor_count"),
    )
    .withColumn(
        "average_return",
        F.when(F.col("total_cost") > 0, F.round((F.col("total_aum") - F.col("total_cost")) / F.col("total_cost") * 100, 2))
         .otherwise(F.lit(0.0)),
    )
)

scheme_count_by_amc = dim_scheme.groupBy("amc_id").agg(F.countDistinct("scheme_id").alias("scheme_count"))

amc_business = (
    dim_amc.select("amc_id", "amc_name")
    .join(amc_scheme_stats, "amc_id", "left")
    .join(scheme_count_by_amc, "amc_id", "left")
    .fillna({"total_aum": 0.0, "investor_count": 0, "scheme_count": 0, "average_return": 0.0})
    .select("amc_id", "amc_name", "total_aum", "investor_count", "scheme_count", "average_return")
)
amc_business.write.mode("overwrite").saveAsTable("mart.amc_business")
print(f"mart.amc_business -> {amc_business.count()} rows")

# COMMAND ----------

# MAGIC %md ## 8. Executive Dashboard Mart
# MAGIC Grain: single row — current snapshot for leadership reporting.
# MAGIC
# MAGIC **Assumption:** `total_investment` = cumulative gross purchase amount (all-time,
# MAGIC from `fact_transactions`), not the current cost basis — this is a "money in the
# MAGIC door, all-time" figure, distinct from `total_aum` which is current market value.

# COMMAND ----------

total_clients = dim_client.select("client_id").distinct().count()
total_advisors = dim_advisor.filter(F.col("status") == "ACTIVE").select("advisor_id").distinct().count()
total_aum = latest_aum.agg(F.sum("market_value")).first()[0] or 0.0
total_investment = fact_transactions.agg(F.sum("amount")).first()[0] or 0.0
total_redemption = fact_redemptions.agg(F.sum("redeemed_amount")).first()[0] or 0.0
total_revenue = fact_commissions.agg(F.sum("commission_amount")).first()[0] or 0.0
active_sips = spark.table("silver.sip_registrations").filter(F.col("status") == "ACTIVE").select("sip_id").distinct().count()
active_schemes = latest_aum.filter(F.col("units_held") > 0).select("scheme_key").distinct().count()

executive_dashboard = spark.createDataFrame(
    [(total_clients, total_advisors, total_aum, total_investment, total_redemption,
      total_revenue, active_sips, active_schemes)],
    ["total_clients", "total_advisors", "total_aum", "total_investment", "total_redemption",
     "total_revenue", "active_sips", "active_schemes"],
).withColumn("dashboard_date", F.current_date())

executive_dashboard.write.mode("overwrite").saveAsTable("mart.executive_dashboard")
executive_dashboard.show(truncate=False)

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT table_name FROM information_schema.tables WHERE table_schema = 'mart' ORDER BY table_name;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Checklist

