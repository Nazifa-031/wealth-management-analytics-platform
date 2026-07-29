# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Setup
# MAGIC Creates the schemas used by the pipeline: `raw`, `bronze`, `silver`, `warehouse`.
# MAGIC
# MAGIC Runs against your **current default catalog** (no catalog name is hard-coded, since
# MAGIC Databricks Free Edition assigns you a workspace catalog automatically — usually
# MAGIC `workspace`). If you want to target a specific catalog, uncomment and edit the
# MAGIC `USE CATALOG` line below.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- USE CATALOG your_catalog_name;
# MAGIC
# MAGIC CREATE SCHEMA IF NOT EXISTS raw;
# MAGIC CREATE SCHEMA IF NOT EXISTS bronze;
# MAGIC CREATE SCHEMA IF NOT EXISTS silver;
# MAGIC CREATE SCHEMA IF NOT EXISTS warehouse;

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW SCHEMAS;

# COMMAND ----------

# MAGIC %md
# MAGIC Next: run `01_data_generation` to populate the `raw` schema.
