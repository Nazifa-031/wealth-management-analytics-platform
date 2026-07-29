# Databricks notebook source
# MAGIC %md
# MAGIC # Warehouse Layer — Completion Checklist
# MAGIC Verifies all 11 warehouse tables exist and are populated.


# COMMAND ----------

dimension_tables = ["dim_client", "dim_advisor", "dim_amc", "dim_scheme", "dim_goal", "dim_time"]
fact_tables = ["fact_transactions", "fact_sip_installments", "fact_redemptions",
               "fact_commissions", "fact_portfolio_aum"]

def check_tables(table_list, label):
    print(f"\n{label} Tables")
    print("-" * 40)
    total_rows = 0
    all_ok = True
    for t in table_list:
        try:
            count = spark.table(f"warehouse.{t}").count()
            status = "✅" if count > 0 else "⚠️  EMPTY"
            if count == 0:
                all_ok = False
            total_rows += count
            print(f"{status}  {t:28s} {count:>8,} rows")
        except Exception as e:
            all_ok = False
            print(f"❌  {t:28s} MISSING  ({str(e).splitlines()[0]})")
    return all_ok, total_rows

dim_ok, dim_rows = check_tables(dimension_tables, "Dimension")
fact_ok, fact_rows = check_tables(fact_tables, "Fact")

print("\n" + "=" * 40)
print("SUMMARY")
print("=" * 40)
print(f"Total Dimensions : {len(dimension_tables)}  {'✅ all present' if dim_ok else '⚠️  check above'}")
print(f"Total Facts      : {len(fact_tables)}  {'✅ all present' if fact_ok else '⚠️  check above'}")
print(f"Total Tables     : {len(dimension_tables) + len(fact_tables)}")
print(f"Total Rows       : {dim_rows + fact_rows:,}")
print("=" * 40)
if dim_ok and fact_ok:
    print("🎉 Warehouse layer complete — matches design doc spec.")
else:
    print("⚠️  One or more tables missing/empty — re-run 04_warehouse_layer.py")

# COMMAND ----------

# MAGIC %md ### trying in sql

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 'Dimension' AS table_type, 'dim_client' AS table_name, COUNT(*) AS row_count FROM warehouse.dim_client
# MAGIC UNION ALL SELECT 'Dimension', 'dim_advisor', COUNT(*) FROM warehouse.dim_advisor
# MAGIC UNION ALL SELECT 'Dimension', 'dim_amc', COUNT(*) FROM warehouse.dim_amc
# MAGIC UNION ALL SELECT 'Dimension', 'dim_scheme', COUNT(*) FROM warehouse.dim_scheme
# MAGIC UNION ALL SELECT 'Dimension', 'dim_goal', COUNT(*) FROM warehouse.dim_goal
# MAGIC UNION ALL SELECT 'Dimension', 'dim_time', COUNT(*) FROM warehouse.dim_time
# MAGIC UNION ALL SELECT 'Fact', 'fact_transactions', COUNT(*) FROM warehouse.fact_transactions
# MAGIC UNION ALL SELECT 'Fact', 'fact_sip_installments', COUNT(*) FROM warehouse.fact_sip_installments
# MAGIC UNION ALL SELECT 'Fact', 'fact_redemptions', COUNT(*) FROM warehouse.fact_redemptions
# MAGIC UNION ALL SELECT 'Fact', 'fact_commissions', COUNT(*) FROM warehouse.fact_commissions
# MAGIC UNION ALL SELECT 'Fact', 'fact_portfolio_aum', COUNT(*) FROM warehouse.fact_portfolio_aum
# MAGIC ORDER BY table_type DESC, table_name;
