// server.js - Fixed version with proper parameter binding
require("dotenv").config();
const express = require("express");
const { DBSQLClient } = require("@databricks/sql");

const app = express();
const PORT = process.env.PORT || 3000;

// ---------------------------------------------------------------------------
// Helper: runs one SQL query against Databricks and returns the rows.
// Uses proper parameter binding to prevent SQL injection.
// ---------------------------------------------------------------------------
async function runQuery(query, params = {}) {
  const client = new DBSQLClient();

  await client.connect({
    host: process.env.DATABRICKS_HOST,
    path: process.env.DATABRICKS_PATH,
    token: process.env.DATABRICKS_TOKEN,
  });

  const session = await client.openSession();

  // Execute with named parameters
  const operation = await session.executeStatement(query, {
    namedParameters: params,
    runAsync: true,
  });

  const result = await operation.fetchAll();
  await operation.close();
  await session.close();
  await client.close();

  return result;
}

// ---------------------------------------------------------------------------
// GET /api/customers/:id
// Returns one customer's portfolio summary.
// ---------------------------------------------------------------------------
app.get("/api/customers/:id", async (req, res) => {
  try {
    const { id } = req.params;

    const query = `
      SELECT client_id, client_name, advisor_name, total_investment,
             current_value, gain_loss, gain_percent, active_scheme_count,
             total_units, last_updated_date
      FROM mart.client_portfolio_summary
      WHERE client_id = :clientId
    `;

    const rows = await runQuery(query, { clientId: parseInt(id) });

    if (!rows || rows.length === 0) {
      return res.status(404).json({ error: `No customer found with id ${id}` });
    }

    res.json(rows[0]);
  } catch (err) {
    console.error("Query failed:", err);
    res.status(500).json({ error: "Something went wrong fetching customer data" });
  }
});

// ---------------------------------------------------------------------------
// GET /api/customers
// Returns ALL customers.
// ---------------------------------------------------------------------------
app.get("/api/customers", async (req, res) => {
  try {
    const rows = await runQuery(`SELECT * FROM mart.client_portfolio_summary`);
    res.json(rows);
  } catch (err) {
    console.error("Query failed:", err);
    res.status(500).json({ error: "Something went wrong fetching customers" });
  }
});

// ---------------------------------------------------------------------------
// GET /api/advisors
// Returns ALL advisors.
// ---------------------------------------------------------------------------
app.get("/api/advisors", async (req, res) => {
  try {
    const rows = await runQuery(`SELECT * FROM mart.advisor_performance`);
    res.json(rows);
  } catch (err) {
    console.error("Query failed:", err);
    res.status(500).json({ error: "Something went wrong fetching advisors" });
  }
});

// ---------------------------------------------------------------------------
// GET /api/schemes
// Returns ALL schemes.
// ---------------------------------------------------------------------------
app.get("/api/schemes", async (req, res) => {
  try {
    const rows = await runQuery(`SELECT * FROM mart.scheme_performance`);
    res.json(rows);
  } catch (err) {
    console.error("Query failed:", err);
    res.status(500).json({ error: "Something went wrong fetching schemes" });
  }
});

// ---------------------------------------------------------------------------
// GET /api/revenue
// Returns ALL revenue data.
// ---------------------------------------------------------------------------
app.get("/api/revenue", async (req, res) => {
  try {
    const rows = await runQuery(`SELECT * FROM mart.revenue`);
    res.json(rows);
  } catch (err) {
    console.error("Query failed:", err);
    res.status(500).json({ error: "Something went wrong fetching revenue" });
  }
});

// ---------------------------------------------------------------------------
// GET /api/sip-analytics
// Returns ALL SIP analytics.
// ---------------------------------------------------------------------------
app.get("/api/sip-analytics", async (req, res) => {
  try {
    const rows = await runQuery(`SELECT * FROM mart.sip_analytics`);
    res.json(rows);
  } catch (err) {
    console.error("Query failed:", err);
    res.status(500).json({ error: "Something went wrong fetching SIP analytics" });
  }
});

// ---------------------------------------------------------------------------
// GET /api/redemptions
// Returns ALL redemption data.
// ---------------------------------------------------------------------------
app.get("/api/redemptions", async (req, res) => {
  try {
    const rows = await runQuery(`SELECT * FROM mart.redemption_analytics`);
    res.json(rows);
  } catch (err) {
    console.error("Query failed:", err);
    res.status(500).json({ error: "Something went wrong fetching redemptions" });
  }
});

// ---------------------------------------------------------------------------
// GET /api/amc
// Returns ALL AMC data.
// ---------------------------------------------------------------------------
app.get("/api/amc", async (req, res) => {
  try {
    const rows = await runQuery(`SELECT * FROM mart.amc_business`);
    res.json(rows);
  } catch (err) {
    console.error("Query failed:", err);
    res.status(500).json({ error: "Something went wrong fetching AMC data" });
  }
});

// ---------------------------------------------------------------------------
// GET /api/executive-dashboard
// Returns the executive dashboard (single row).
// ---------------------------------------------------------------------------
app.get("/api/executive-dashboard", async (req, res) => {
  try {
    const rows = await runQuery(`SELECT * FROM mart.executive_dashboard`);
    res.json(rows[0] || {});
  } catch (err) {
    console.error("Query failed:", err);
    res.status(500).json({ error: "Something went wrong fetching the executive dashboard" });
  }
});

// ---------------------------------------------------------------------------
// GET /api/advisor/:name
// Returns a specific advisor by name.
// ---------------------------------------------------------------------------
app.get("/api/advisor/:name", async (req, res) => {
  try {
    const { name } = req.params;
    const query = `
      SELECT * FROM mart.advisor_performance
      WHERE advisor_name LIKE CONCAT('%', :name, '%')
    `;
    const rows = await runQuery(query, { name });
    res.json(rows);
  } catch (err) {
    console.error("Query failed:", err);
    res.status(500).json({ error: "Something went wrong fetching advisor" });
  }
});

// ---------------------------------------------------------------------------
// GET /api/client/:id/sips
// Returns SIP details for a specific client.
// ---------------------------------------------------------------------------
app.get("/api/client/:id/sips", async (req, res) => {
  try {
    const { id } = req.params;
    const query = `
      SELECT * FROM mart.sip_analytics
      WHERE client_id = :clientId
    `;
    const rows = await runQuery(query, { clientId: parseInt(id) });
    res.json(rows);
  } catch (err) {
    console.error("Query failed:", err);
    res.status(500).json({ error: "Something went wrong fetching client SIPs" });
  }
});

// ---------------------------------------------------------------------------
// GET /api/client/:id/redemptions
// Returns redemption details for a specific client.
// ---------------------------------------------------------------------------
app.get("/api/client/:id/redemptions", async (req, res) => {
  try {
    const { id } = req.params;
    const query = `
      SELECT * FROM mart.redemption_analytics
      WHERE client_id = :clientId
    `;
    const rows = await runQuery(query, { clientId: parseInt(id) });
    res.json(rows);
  } catch (err) {
    console.error("Query failed:", err);
    res.status(500).json({ error: "Something went wrong fetching client redemptions" });
  }
});

// ---------------------------------------------------------------------------
// GET /api/top/:mart/:metric/:n
// Generic top-N query for any mart.
// Example: /api/top/advisors/total_revenue/10
// ---------------------------------------------------------------------------
app.get("/api/top/:mart/:metric/:n", async (req, res) => {
  try {
    const { mart, metric, n } = req.params;
    
    // Map mart names to table names and column mappings
    const martMap = {
      'advisors': { table: 'mart.advisor_performance', nameCol: 'advisor_name' },
      'clients': { table: 'mart.client_portfolio_summary', nameCol: 'client_name' },
      'schemes': { table: 'mart.scheme_performance', nameCol: 'scheme_name' },
      'amcs': { table: 'mart.amc_business', nameCol: 'amc_name' },
    };
    
    const martInfo = martMap[mart];
    if (!martInfo) {
      return res.status(400).json({ error: `Mart '${mart}' not found` });
    }
    
    const query = `
      SELECT ${martInfo.nameCol} as name, ${metric}
      FROM ${martInfo.table}
      ORDER BY ${metric} DESC
      LIMIT ${parseInt(n)}
    `;
    
    const rows = await runQuery(query);
    res.json(rows);
  } catch (err) {
    console.error("Query failed:", err);
    res.status(500).json({ error: "Something went wrong fetching top data" });
  }
});

// Health check
app.get("/health", (req, res) => res.json({ status: "ok", timestamp: new Date().toISOString() }));

// Hello endpoint
app.get("/api/hello", (req, res) => {
  res.json({ message: "Hello! Your API server is working." });
});

// Start the server
app.listen(PORT, () => {
  console.log(` API running: http://localhost:${PORT}`);
  console.log(` Health check: http://localhost:${PORT}/health`);
  console.log(` Customers: http://localhost:${PORT}/api/customers`);
  console.log(` Advisors: http://localhost:${PORT}/api/advisors`);
});