# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Setup
# MAGIC Creates the schemas used by the pipeline: `raw`, `bronze`, `silver`, `warehouse`.


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


