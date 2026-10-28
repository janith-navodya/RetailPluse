# RetailPulse DI: Resume Bullet Points & LinkedIn Showcase Package

---

## 1. Resume / CV Tailored Bullet Points

### For Business Intelligence & Analytics Engineer Roles:
- **Architected Kimball Star Schema in Microsoft SQL Server 2025** featuring 4 dimension and 4 fact tables across 231,000+ retail transactions; designed 8 production analytical views and Power BI semantic model with 15+ verified DAX measures (`[Days of Supply]`, `[Gross Margin %]`, `[Annualized Turnover]`).
- **Engineered Automated Cross-Engine Metric Reconciliation Harness** using Pytest and Pandas, validating identical mathematical parity ($\le 0.01$ tolerance) across T-SQL views, Python pipelines, and Power BI DAX formulas to eliminate corporate reporting discrepancies.
- **Built Interactive Executive Decision Portal in Streamlit** delivering real-time Days of Supply histograms, category working capital breakdowns, and human-in-the-loop purchase order approval workflows with idempotent SQL Server write-back.

### For Data Engineer Roles:
- **Built Resilient, Idempotent Retail Data Pipeline** in Python 3.13 and Microsoft SQL Server utilizing Pydantic V2 schema validation and bulk T-SQL `MERGE` execution with `fast_executemany`, processing 231,200 records with zero duplicate insertion.
- **Designed Dead-Letter Quarantine Architecture** isolating malformed transactions (negative pricing, orphaned keys, invalid calendar dates) into `dbo.quarantine_records` with raw JSON payloads and execution lineage for zero-loss auditability.
- **Enforced 100% Parameterized Query Execution & Windows Integrated Security** with SQLAlchemy 2.x and ODBC Driver 18, hardening database interaction against SQL injection and eliminating stored credential vulnerabilities.

### For Applied Machine Learning & Operations Research Roles:
- **Formulated Demand Uncensoring Engine for Retail Stockouts**, reconstructing latent consumer demand during stockout periods using moving baseline imputation; eliminated an empirical -17.19% down-forecasting bias and reduced WAPE from 36.19% to 27.37%.
- **Developed Probabilistic Quantile Forecasting Suite ($P_{10}, P_{50}, P_{90}$)** using LightGBM regressor with Pinball Loss on 100% leak-free rolling-origin lag features, dynamically hedging against supplier lead-time variance.
- **Developed Mixed-Integer Linear Programming (MILP) Replenishment Optimizer** in Python via SciPy HiGHS simplex solver, optimizing multi-item order allocations under working-capital budget ceilings, supplier MOQs, and discrete carton pack sizes in $<10\text{ms}$.
- **Conducted 30-Day Forward Policy Simulation** demonstrating that constrained MILP replenishment achieved 0.96x capital efficiency while deploying 60.5% less working capital and reducing inventory holding costs by 61.3% compared to naive periodic ordering.

---

## 2. Ready-to-Publish LinkedIn Project Showcase Post

```markdown
🚀 Excited to share my latest project: RetailPulse DI — a production-grade Decision Intelligence & Inventory Replenishment Platform!

Most retail forecasting projects suffer from a fundamental flaw: "The Inventory Death Spiral." When an item stocks out, recorded sales drop to zero. Standard ML models trained on raw sales interpret this as zero customer interest, lowering future forecasts and triggering smaller replenishment orders in a self-fulfilling downward trap.

To solve this, I built RetailPulse DI: an end-to-end Decision Intelligence system connecting dimensional data engineering, time-series demand uncensoring, and constrained operations research optimization.

🔍 Technical Highlights:

1️⃣ Enterprise Data Foundation (SQL Server & Pydantic):
- Architected a Kimball Star Schema with 4 dimensions and 4 fact tables across 231,000+ retail records.
- Built an idempotent ingestion pipeline using Pydantic V2 validation and a dead-letter quarantine table (`quarantine_records`) isolating anomalies with execution lineage.
- Enforced 100% parameterized queries via SQLAlchemy 2.x and Windows Integrated Security (-E).

2️⃣ Demand Uncensoring & Quantile ML (LightGBM):
- Reconstructed latent demand during zero-inventory stockout days using localized rate-of-sale baselines.
- Walk-forward rolling-origin evaluation proved that uncensoring eliminated a -17.19% down-forecasting bias (reducing bias to +0.20%) and cut WAPE by 8.8 percentage points.
- Trained monotonic Quantile Regressors (P10, P50, P90) to generate lead-time uncertainty fan charts without fragile Gaussian assumptions.

3️⃣ Constrained Replenishment Engine (HiGHS MILP):
- Real retail replenishment is not unconstrained ROP—it is a Knapsack problem constrained by working capital budget caps, supplier Minimum Order Quantities (MOQs), and discrete carton pack multiples.
- Formulated and solved Mixed-Integer Linear Programs (MILP) in Python via SciPy HiGHS, achieving sub-10ms convergence across multi-item retail fleets.
- A 30-day forward simulation showed our MILP policy achieved a 0.96x capital efficiency ratio, saving 60.5% in deployed procurement capital and 61.3% in holding costs vs naive periodic ordering.

4️⃣ Operational Streamlit Portal & Power BI Semantic Model:
- Built a 4-page Streamlit portal for executive KPI monitoring, demand uncertainty visualization, live MILP parameter solving, and one-click database approval write-back.
- Built an automated Pytest reconciliation harness guaranteeing mathematical alignment (<=0.01 tolerance) across SQL Server views, Python algorithms, and Power BI DAX formulas.

🛡️ Quality & Testing:
63/63 automated tests passing (100% green across unit, integration, reconciliation, forecasting, replenishment, resilience, and headless UI smoke tests).

Check out the full open-source codebase, architecture documentation, and viva defense guide on GitHub:
👉 [Link to Repository]

#DataEngineering #MachineLearning #DecisionIntelligence #OperationsResearch #SupplyChain #Python #SQLServer #PowerBI #Streamlit #DataScience
```
