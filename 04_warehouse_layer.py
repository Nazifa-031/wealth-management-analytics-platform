# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Warehouse Layer (Star Schema)
# MAGIC Builds the dimension and fact tables defined in the Phase 2 design doc, reading
# MAGIC from `silver.*` and writing to `warehouse.*`.
# MAGIC
# MAGIC **Dimensions:** dim_client, dim_advisor, dim_amc, dim_scheme, dim_goal, dim_time
# MAGIC **Facts:** fact_transactions, fact_sip_installments, fact_redemptions,
# MAGIC fact_commissions, fact_portfolio_aum

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

# COMMAND ----------

# MAGIC %md ## dim_time
# MAGIC Generated calendar table. Covers the full date range used by any fact table.
# MAGIC Indian financial year: Apr–Mar.

# COMMAND ----------

date_range = spark.sql("""
    SELECT explode(sequence(to_date('2023-01-01'), to_date('2026-12-31'), interval 1 day)) AS full_date
""")

dim_time = (
    date_range
    .withColumn("date_key", F.date_format("full_date", "yyyyMMdd").cast("int"))
    .withColumn("day", F.dayofmonth("full_date"))
    .withColumn("month", F.month("full_date"))
    .withColumn("month_name", F.date_format("full_date", "MMMM"))
    .withColumn("quarter", F.quarter("full_date"))
    .withColumn("year", F.year("full_date"))
    .withColumn(
        "financial_year",
        F.when(F.col("month") >= 4,
               F.concat(F.col("year"), F.lit("-"), (F.col("year") + 1).cast("string")))
         .otherwise(F.concat((F.col("year") - 1).cast("string"), F.lit("-"), F.col("year")))
    )
    .select("date_key", "full_date", "day", "month", "month_name", "quarter", "year", "financial_year")
)

dim_time.write.mode("overwrite").saveAsTable("warehouse.dim_time")
print(f"warehouse.dim_time -> {dim_time.count()} rows")

# COMMAND ----------

# MAGIC %md ## dim_client
# MAGIC Source: `clients`, `risk_profiles`. NOTE: the design doc's `clients` source table
# MAGIC already carries `city`/`state`; in this build those live in `client_addresses`,
# MAGIC so we join that in too to populate the same target columns.

# COMMAND ----------

clients = spark.table("silver.clients")
risk_profiles = spark.table("silver.risk_profiles")
addresses = spark.table("silver.client_addresses")

dim_client = (
    clients.alias("c")
    .join(risk_profiles.alias("rp"), F.col("c.client_id") == F.col("rp.client_id"), "left")
    .join(addresses.alias("a"), F.col("c.client_id") == F.col("a.client_id"), "left")
    .select(
        F.row_number().over(Window.orderBy("c.client_id")).alias("client_key"),
        F.col("c.client_id"),
        F.col("c.client_name"),
        F.col("c.dob"),
        F.col("c.pan"),
        F.col("c.mobile"),
        F.col("c.email"),
        F.col("a.city"),
        F.col("a.state"),
        F.col("c.advisor_id"),
        F.col("rp.risk_category"),
        F.col("rp.risk_score"),
        F.col("c.onboarding_date"),
    )
)
dim_client.write.mode("overwrite").saveAsTable("warehouse.dim_client")
print(f"warehouse.dim_client -> {dim_client.count()} rows")

# COMMAND ----------

# MAGIC %md ## dim_advisor
# MAGIC Source: `advisors`, `branches`, `regions`. NOTE: the design doc includes a `zone`
# MAGIC column with no defined source; we derive it as equal to `region_name` — replace
# MAGIC with real zone-mapping logic if your source systems define zones separately.

# COMMAND ----------

advisors = spark.table("silver.advisors")
branches = spark.table("silver.branches")
regions = spark.table("silver.regions")

dim_advisor = (
    advisors.alias("adv")
    .join(branches.alias("b"), F.col("adv.branch_id") == F.col("b.branch_id"), "left")
    .join(regions.alias("r"), F.col("b.region_id") == F.col("r.region_id"), "left")
    .select(
        F.row_number().over(Window.orderBy("adv.advisor_id")).alias("advisor_key"),
        F.col("adv.advisor_id"),
        F.col("adv.advisor_name"),
        F.col("b.branch_id"),
        F.col("b.branch_name"),
        F.col("b.city"),
        F.col("r.region_id"),
        F.col("r.region_name"),
        F.col("r.region_name").alias("zone"),
        F.col("adv.joining_date"),
        F.col("adv.status"),
    )
)
dim_advisor.write.mode("overwrite").saveAsTable("warehouse.dim_advisor")
print(f"warehouse.dim_advisor -> {dim_advisor.count()} rows")

# COMMAND ----------

# MAGIC %md ## dim_amc

# COMMAND ----------

dim_amc = (
    spark.table("silver.amcs")
    .select(
        F.row_number().over(Window.orderBy("amc_id")).alias("amc_key"),
        "amc_id", "amc_name",
    )
)
dim_amc.write.mode("overwrite").saveAsTable("warehouse.dim_amc")
print(f"warehouse.dim_amc -> {dim_amc.count()} rows")

# COMMAND ----------

# MAGIC %md ## dim_scheme
# MAGIC Source: `schemes`, `scheme_categories`, `amcs`.

# COMMAND ----------

schemes = spark.table("silver.schemes")
categories = spark.table("silver.scheme_categories")
amcs = spark.table("silver.amcs")

dim_scheme = (
    schemes.alias("s")
    .join(categories.alias("cat"), F.col("s.category_id") == F.col("cat.category_id"), "left")
    .join(amcs.alias("a"), F.col("s.amc_id") == F.col("a.amc_id"), "left")
    .select(
        F.row_number().over(Window.orderBy("s.scheme_id")).alias("scheme_key"),
        F.col("s.scheme_id"),
        F.col("s.scheme_name"),
        F.col("s.amc_id"),
        F.col("a.amc_name"),
        F.col("s.category_id"),
        F.col("cat.category_name"),
        F.col("s.asset_class"),
        F.col("s.risk_level"),
        F.col("s.expense_ratio"),
    )
)
dim_scheme.write.mode("overwrite").saveAsTable("warehouse.dim_scheme")
print(f"warehouse.dim_scheme -> {dim_scheme.count()} rows")

# COMMAND ----------

# MAGIC %md ## dim_goal

# COMMAND ----------

dim_goal = (
    spark.table("silver.goals")
    .select(
        F.row_number().over(Window.orderBy("goal_id")).alias("goal_key"),
        "goal_id", "goal_name", "target_amount", "target_date",
    )
)
dim_goal.write.mode("overwrite").saveAsTable("warehouse.dim_goal")
print(f"warehouse.dim_goal -> {dim_goal.count()} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Reusable lookups
# MAGIC Small broadcastable frames used repeatedly by the fact builds below.

# COMMAND ----------

dim_client_l = spark.table("warehouse.dim_client").select("client_key", "client_id", "advisor_id")
dim_advisor_l = spark.table("warehouse.dim_advisor").select("advisor_key", "advisor_id")
dim_scheme_l = spark.table("warehouse.dim_scheme").select("scheme_key", "scheme_id")
folios = spark.table("silver.folios").select("folio_id", "client_id")

# client_id -> client_key/advisor_key, resolved once
client_advisor_lookup = (
    dim_client_l.join(dim_advisor_l, "advisor_id", "left")
    .select("client_id", "client_key", "advisor_key")
)

# COMMAND ----------

# MAGIC %md ## fact_transactions
# MAGIC Grain: one row per transaction.

# COMMAND ----------

transactions = spark.table("silver.transactions")

fact_transactions = (
    transactions.alias("t")
    .join(folios.alias("f"), F.col("t.folio_id") == F.col("f.folio_id"), "left")
    .join(client_advisor_lookup.alias("ca"), F.col("f.client_id") == F.col("ca.client_id"), "left")
    .join(dim_scheme_l.alias("sc"), F.col("t.scheme_id") == F.col("sc.scheme_id"), "left")
    .select(
        F.row_number().over(Window.orderBy("t.transaction_id")).alias("transaction_key"),
        F.col("t.transaction_id"),
        F.col("ca.client_key"),
        F.col("ca.advisor_key"),
        F.col("sc.scheme_key"),
        F.date_format("t.transaction_date", "yyyyMMdd").cast("int").alias("date_key"),
        F.col("t.folio_id"),
        F.col("t.transaction_type"),
        F.col("t.amount"),
        F.col("t.units"),
        F.col("t.nav"),
    )
)
fact_transactions.write.mode("overwrite").saveAsTable("warehouse.fact_transactions")
print(f"warehouse.fact_transactions -> {fact_transactions.count()} rows")

# COMMAND ----------

# MAGIC %md ## fact_sip_installments
# MAGIC Grain: one row per SIP installment.

# COMMAND ----------

sip_installments = spark.table("silver.sip_installments")
sip_registrations = spark.table("silver.sip_registrations").select("sip_id", "folio_id", "scheme_id")

fact_sip_installments = (
    sip_installments.alias("si")
    .join(sip_registrations.alias("sr"), "sip_id", "left")
    .join(folios.alias("f"), F.col("sr.folio_id") == F.col("f.folio_id"), "left")
    .join(client_advisor_lookup.alias("ca"), F.col("f.client_id") == F.col("ca.client_id"), "left")
    .join(dim_scheme_l.alias("sc"), F.col("sr.scheme_id") == F.col("sc.scheme_id"), "left")
    .select(
        F.row_number().over(Window.orderBy("si.sip_installment_id")).alias("sip_installment_key"),
        F.col("si.sip_id"),
        F.col("ca.client_key"),
        F.col("ca.advisor_key"),
        F.col("sc.scheme_key"),
        F.date_format("si.installment_date", "yyyyMMdd").cast("int").alias("date_key"),
        F.col("si.installment_amount"),
        F.col("si.units"),
        F.col("si.nav"),
    )
)
fact_sip_installments.write.mode("overwrite").saveAsTable("warehouse.fact_sip_installments")
print(f"warehouse.fact_sip_installments -> {fact_sip_installments.count()} rows")

# COMMAND ----------

# MAGIC %md ## fact_redemptions
# MAGIC Grain: one row per redemption.

# COMMAND ----------

redemptions = spark.table("silver.redemption_transactions")

fact_redemptions = (
    redemptions.alias("r")
    .join(folios.alias("f"), F.col("r.folio_id") == F.col("f.folio_id"), "left")
    .join(client_advisor_lookup.alias("ca"), F.col("f.client_id") == F.col("ca.client_id"), "left")
    .join(dim_scheme_l.alias("sc"), F.col("r.scheme_id") == F.col("sc.scheme_id"), "left")
    .select(
        F.row_number().over(Window.orderBy("r.redemption_id")).alias("redemption_key"),
        F.col("r.redemption_id"),
        F.col("ca.client_key"),
        F.col("ca.advisor_key"),
        F.col("sc.scheme_key"),
        F.date_format("r.redemption_date", "yyyyMMdd").cast("int").alias("date_key"),
        F.col("r.redeemed_amount"),
        F.col("r.redeemed_units"),
        F.col("r.nav"),
    )
)
fact_redemptions.write.mode("overwrite").saveAsTable("warehouse.fact_redemptions")
print(f"warehouse.fact_redemptions -> {fact_redemptions.count()} rows")

# COMMAND ----------

# MAGIC %md ## fact_commissions
# MAGIC Grain: one row per commission event. Unions `brokerage` (upfront) and
# MAGIC `trail_commissions` (recurring trail) into a single fact.

# COMMAND ----------

brokerage = spark.table("silver.brokerage")
trail = spark.table("silver.trail_commissions")

brokerage_fact = (
    brokerage.alias("b")
    .join(dim_advisor_l.alias("adv"), F.col("b.advisor_id") == F.col("adv.advisor_id"), "left")
    .join(dim_scheme_l.alias("sc"), F.col("b.scheme_id") == F.col("sc.scheme_id"), "left")
    .select(
        F.col("adv.advisor_key"),
        F.col("sc.scheme_key"),
        F.date_format("b.commission_date", "yyyyMMdd").cast("int").alias("date_key"),
        F.lit("BROKERAGE").alias("commission_type"),
        F.col("b.commission_amount"),
    )
)

trail_fact = (
    trail.alias("tc")
    .join(dim_advisor_l.alias("adv"), F.col("tc.advisor_id") == F.col("adv.advisor_id"), "left")
    .join(dim_scheme_l.alias("sc"), F.col("tc.scheme_id") == F.col("sc.scheme_id"), "left")
    .select(
        F.col("adv.advisor_key"),
        F.col("sc.scheme_key"),
        F.date_format("tc.commission_month", "yyyyMMdd").cast("int").alias("date_key"),
        F.lit("TRAIL").alias("commission_type"),
        F.col("tc.commission_amount"),
    )
)

fact_commissions = (
    brokerage_fact.unionByName(trail_fact)
    .withColumn("commission_key", F.row_number().over(Window.orderBy(F.monotonically_increasing_id())))
    .select("commission_key", "advisor_key", "scheme_key", "date_key", "commission_type", "commission_amount")
)
fact_commissions.write.mode("overwrite").saveAsTable("warehouse.fact_commissions")
print(f"warehouse.fact_commissions -> {fact_commissions.count()} rows")

# COMMAND ----------

# MAGIC %md ## fact_portfolio_aum
# MAGIC Grain: one row per client + scheme + day.



# COMMAND ----------

# 1. Unit-changing events, normalized to (client_id, scheme_id, event_date, units_delta, cost_delta)
purchase_events = (
    transactions.select(
        F.col("folio_id"), F.col("scheme_id"),
        F.col("transaction_date").alias("event_date"),
        F.col("units").alias("units_delta"),
        F.col("amount").alias("cost_delta"),
    )
)

sip_events = (
    sip_installments.alias("si")
    .join(sip_registrations.alias("sr"), "sip_id", "left")
    .select(
        F.col("sr.folio_id"), F.col("sr.scheme_id"),
        F.col("si.installment_date").alias("event_date"),
        F.col("si.units").alias("units_delta"),
        F.col("si.installment_amount").alias("cost_delta"),
    )
)

redemption_events = (
    redemptions.select(
        F.col("folio_id"), F.col("scheme_id"),
        F.col("redemption_date").alias("event_date"),
        (-F.col("redeemed_units")).alias("units_delta"),
        (-F.col("redeemed_amount")).alias("cost_delta"),
    )
)

all_events = purchase_events.unionByName(sip_events).unionByName(redemption_events)

client_scheme_events = (
    all_events.alias("e")
    .join(folios.alias("f"), F.col("e.folio_id") == F.col("f.folio_id"), "left")
    .groupBy("f.client_id", "e.scheme_id", "e.event_date")
    .agg(F.sum("units_delta").alias("units_delta"), F.sum("cost_delta").alias("cost_delta"))
)

# 2. Running cumulative units/cost per client+scheme, ordered by date
cum_window = (
    Window.partitionBy("client_id", "scheme_id")
    .orderBy("event_date")
    .rowsBetween(Window.unboundedPreceding, Window.currentRow)
)

cumulative = (
    client_scheme_events
    .withColumn("cum_units", F.sum("units_delta").over(cum_window))
    .withColumn("cum_cost", F.sum("cost_delta").over(cum_window))
    .withColumnRenamed("event_date", "as_of_date")
)

# 3. Forward-fill cumulative units/cost onto every NAV date for that scheme
nav_history = spark.table("silver.nav_history")

# distinct (client_id, scheme_id) pairs that ever had activity
client_scheme_pairs = cumulative.select("client_id", "scheme_id").distinct()

nav_scaffold = (
    client_scheme_pairs.alias("p")
    .join(nav_history.alias("n"), F.col("p.scheme_id") == F.col("n.scheme_id"))
    .select("p.client_id", "p.scheme_id", F.col("n.nav_date"), F.col("n.nav"))
)

timeline = (
    nav_scaffold
    .join(
        cumulative.withColumnRenamed("as_of_date", "nav_date"),
        on=["client_id", "scheme_id", "nav_date"],
        how="left",
    )
)

ffill_window = (
    Window.partitionBy("client_id", "scheme_id")
    .orderBy("nav_date")
    .rowsBetween(Window.unboundedPreceding, Window.currentRow)
)

filled = (
    timeline
    .withColumn("units_held", F.last("cum_units", ignorenulls=True).over(ffill_window))
    .withColumn("cost_value", F.last("cum_cost", ignorenulls=True).over(ffill_window))
    .fillna({"units_held": 0.0, "cost_value": 0.0})
    .withColumn("market_value", F.col("units_held") * F.col("nav"))
    .withColumn("gain_loss", F.col("market_value") - F.col("cost_value"))
)

fact_portfolio_aum = (
    filled.alias("x")
    .join(client_advisor_lookup.alias("ca"), "client_id", "left")
    .join(dim_scheme_l.alias("sc"), "scheme_id", "left")
    .select(
        F.row_number().over(Window.orderBy("x.client_id", "x.scheme_id", "x.nav_date")).alias("aum_key"),
        F.col("ca.client_key"),
        F.col("ca.advisor_key"),
        F.col("sc.scheme_key"),
        F.date_format("x.nav_date", "yyyyMMdd").cast("int").alias("date_key"),
        F.col("x.units_held"),
        F.col("x.nav").alias("latest_nav"),
        F.col("x.market_value"),
        F.col("x.cost_value"),
        F.col("x.gain_loss"),
    )
)
fact_portfolio_aum.write.mode("overwrite").saveAsTable("warehouse.fact_portfolio_aum")
print(f"warehouse.fact_portfolio_aum -> {fact_portfolio_aum.count()} rows")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT table_name FROM information_schema.tables WHERE table_schema = 'warehouse' ORDER BY table_name;

# COMMAND ----------

# MAGIC %md
# MAGIC ## check: AUM reporting
# MAGIC Quick spot check that the star schema actually answers a business question —
# MAGIC total AUM per advisor as of the most recent date.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   a.advisor_name,
# MAGIC   ROUND(SUM(f.market_value), 2) AS total_aum
# MAGIC FROM warehouse.fact_portfolio_aum f
# MAGIC JOIN warehouse.dim_advisor a ON f.advisor_key = a.advisor_key
# MAGIC JOIN warehouse.dim_time t ON f.date_key = t.date_key
# MAGIC WHERE t.full_date = (SELECT MAX(full_date) FROM warehouse.dim_time WHERE date_key IN (SELECT date_key FROM warehouse.fact_portfolio_aum))
# MAGIC GROUP BY a.advisor_name
# MAGIC ORDER BY total_aum DESC
# MAGIC LIMIT 10;
