# RetailPulse DI: 3-Minute Live Recruiter & Technical Demonstration Script

> **Goal:** Deliver a concise, high-impact 3-minute live technical walkthrough of the RetailPulse Decision Intelligence Platform to an engineering hiring manager or technical recruiter.

---

## Pre-Demo Quickstart
Open PowerShell in the project directory and launch the application:
```powershell
.venv\Scripts\Activate.ps1
streamlit run app.py
```
*The portal opens automatically at `http://localhost:8501`.*

---

## ⏱️ MINUTE 1: Executive Fleet Health & Semantic Parity (0:00 - 1:00)

### Action:
1. Navigate to **Page 1: Executive KPI Cockpit**.
2. Point out the top 4 KPI cards and the Days of Supply distribution chart.
3. Switch briefly to **Page 4: Data Observability & Audit**.

### Talking Points:
> *"Hi, I'd like to show you RetailPulse DI. Most retail inventory dashboards are descriptive—they show sales that already happened. RetailPulse is a **prescriptive Decision Intelligence platform** that links data engineering, machine learning, and mathematical optimization to automate daily replenishment under real-world constraints.*
> 
> *Here on the **Executive Cockpit**, you see real-time fleet health across 50 SKUs: a 37.62% Gross Margin, 28.5 Days of Supply, and 14 active stockouts. Over \$34,000 is currently trapped in excess inventory with more than 45 days of supply.*
> 
> *Notice that we don't just calculate numbers in the frontend. On **Page 4**, our automated test harness proves exact mathematical alignment across our Microsoft SQL Server views, Python Pandas pipeline, and Power BI DAX formulas within a 0.01 tolerance.*
> 
> *Furthermore, our Pydantic ingestion firewall automatically isolated 60 corrupted transactions into a dead-letter quarantine table—capturing raw JSON payloads and error codes without disrupting clean operations."*

---

## ⏱️ MINUTE 2: Demand Uncensoring & Quantile Fan Charts (1:00 - 2:00)

### Action:
1. Navigate to **Page 2: Demand & Uncertainty**.
2. Select Store `STR01` and SKU `PRD01` or `PRD06`.
3. Highlight the red 'x' stockout imputation events on the historical overlay chart.
4. Adjust the **Lead Time Horizon Slider** from 7 to 14 days to show the fan chart expanding dynamically.

### Talking Points:
> *"Now let's examine the core machine learning problem in retail: **Censored Demand**. When an item stocks out, recorded sales drop to zero. If you train a standard XGBoost or regression model on raw sales, the algorithm assumes zero demand, lowering future orders and creating a downward death spiral.*
> 
> *On this chart, the grey line shows observed sales collapsing to zero during stockout days. The blue dashed line is RetailPulse's reconstructed latent demand, which uses localized rate-of-sale baselines to impute true consumer appetite.*
> 
> *In our 730-day walk-forward evaluation, training LightGBM on raw sales produced a **-17.19% under-forecasting bias**. Training on uncensored demand eliminated this bias down to **+0.20%** and cut WAPE by 8.8 percentage points.*
> 
> *Below, rather than predicting a single naive number, we output **Quantile Regressions**: P10 as our conservative downside, P50 as our median operational baseline, and P90 as our risk-hedging safety buffer. Notice how the uncertainty fan widens proportionally to supplier lead-time variance."*

---

## ⏱️ MINUTE 3: Constrained MILP Optimizer & Approval Write-Back (2:00 - 3:00)

### Action:
1. Navigate to **Page 3: Replenishment Engine**.
2. Drag the **Working Capital Budget Slider** from \$15,000 down to \$8,000. Click **"Solve Replenishment MILP"**.
3. Point out how the solver dynamically re-prioritizes high-risk SKUs and maintains 100% compliance with supplier MOQs and pack sizes.
4. Drag the slider up to \$25,000 to show expanded allocation.
5. In the **Manager Approval Section**, click **"Bulk Approve All Positive Orders"**.
6. Show the confirmation toast verifying direct write-back to SQL Server.

### Talking Points:
> *"Finally, here is the decision engine. Most retail tools stop at calculating an unconstrained Reorder Point deficit. But if you have 40 items below ROP and only \$15,000 in cash, how do you decide what to buy?*
> 
> *We formulated replenishment as a **Mixed-Integer Linear Program (MILP)** solved via the HiGHS branch-and-bound solver. It optimizes purchase allocations subject to three strict constraints:*
> 1. *Total order spend cannot exceed the available working capital budget.*
> 2. *Every order must satisfy the supplier's Minimum Order Quantity (MOQ)—you order 0 or at least the MOQ.*
> 3. *Order quantities must be integer multiples of manufacturer carton pack sizes.*
> 
> *Watch this: when I drop the budget from \$15,000 to \$8,000 and hit solve, the MILP solves in under 10 milliseconds. It allocates \$7,950, prioritizing critical stockout risks first while keeping pack sizes integer-compliant.*
> 
> *To complete the loop, managers can review recommendations, override units if necessary, and click 'Bulk Approve'. This executes an idempotent write-back directly into Microsoft SQL Server table `dbo.fact_replenishment_recommendation`.*
> 
> *In our 30-day forward simulation, this constrained approach achieved a **0.96x capital efficiency ratio**, deploying 60% less capital than naive periodic ordering with 61% lower holding costs."*

---

## 🎯 Conclusion (Wrap-up Statement)
> *"RetailPulse DI brings data engineering rigor, time-series machine learning, and operations research optimization together into an end-to-end local production system. All 63 automated tests are green, backed by full Kimball dimensional modeling and clean architecture."*
