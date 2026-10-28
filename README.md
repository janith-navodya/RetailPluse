# RetailPulse DI: Retail Decision Intelligence Platform

> **A local, production-grade Decision Intelligence platform for retail inventory replenishment under censored demand, lead-time uncertainty, and working-capital constraints.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Architecture](https://img.shields.io/badge/architecture-Clean%20Architecture-emerald.svg)](ARCHITECTURE.md)
[![Database](https://img.shields.io/badge/database-Star%20Schema%20(ANSI%20SQL)-orange.svg)](DATA_DICTIONARY.md)
[![Testing](https://img.shields.io/badge/tests-Pytest%20Reconciliation-purple.svg)](METRIC_DEFINITIONS.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 1. Executive Summary

Retail inventory optimization is notoriously vulnerable to two systemic operational flaws:
1. **The Censored Demand Trap ("The Inventory Death Spiral"):** Standard demand forecasting models train on historical *sales* rather than true *demand*. When an item stocks out, recorded sales drop to zero. Naive algorithms mistake stockouts for a lack of customer interest, lowering forecasts and triggering smaller replenishment orders in a self-fulfilling downward spiral.
2. **Disconnected Operational Decisions:** Forecasting models estimate demand in isolation from physical and financial boundaries—ignoring supplier **Minimum Order Quantities (MOQs)**, **discrete pack sizes**, and **corporate working capital budgets**.

**RetailPulse DI** solves both challenges by combining:
- **A Kimball Star Schema & Dead-Letter Quarantine Pipeline:** Enterprise data engineering with Pydantic validation and idempotent loading.
- **Demand Uncensoring & Quantile Time-Series Forecasting:** LightGBM probabilistic regression ($P_{10}, P_{50}, P_{90}$) trained on rolling-origin lag features with zero data leakage.
- **Constrained Replenishment Engine:** Mixed-Integer Linear Programming (MILP via PuLP) optimizing multi-item order quantities under supplier MOQs, case multiples, and budget caps.
- **Automated Metric Reconciliation:** A 3-way test harness proving exact mathematical parity ($\pm 0.01$ tolerance) across SQL Views, Python calculations, and Power BI DAX.
- **Operational & Strategic Cockpits:** An interactive 4-page Streamlit portal paired with a Power BI semantic model.

---

## 2. System Architecture

RetailPulse DI follows **Clean Architecture** principles, enforcing strict inward-facing dependency boundaries:

```
[ Presentation Layer ] ──> Streamlit Operational Portal | Power BI (.pbix)
          │
[ Application Core  ] ──> Quantile Forecaster (LightGBM) | MILP Solver (PuLP) | Analytics
          │
[ Data Engine Layer ] ──> Pydantic Validators | Quarantine Dead-Letter | SQLAlchemy
          │
[ Domain Core       ] ──> Business Entities | Invariants | Mathematical Formulations
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for sequence diagrams, interface contracts, and design patterns.

---

## 3. Repository Structure

```
RetailPlus_AI/
├── ARCHITECTURE.md                  # Comprehensive architectural specification & sequence flows
├── DATA_DICTIONARY.md               # Star Schema DDL, table grains, constraints, and audit columns
├── METRIC_DEFINITIONS.md            # Exact mathematical definitions across SQL, Python, and DAX
├── README.md                        # Project overview and quickstart guide
├── pyproject.toml                   # Project metadata and tool configuration
├── requirements.txt                 # Pinned dependencies
├── config/                          # Centralized settings and structured logging
├── data/
│   ├── raw/                         # Raw ingested transactional feeds
│   ├── processed/                   # Staged and clean data partitions
│   └── quarantine/                  # Dead-letter quarantine logs
├── docs/specs/                      # Formal engineering specifications
├── sql/
│   ├── ddl/                         # ANSI SQL DDL for Fact, Dim, and Quarantine tables
│   └── views/                       # Analytical SQL views for business KPIs
├── src/
│   ├── domain/                      # Pure business entities and mathematical rules
│   ├── data_engine/                 # Pydantic validation, quarantine engine, DB migrations
│   ├── analytics/                   # KPI computation and 3-way reconciliation harness
│   ├── forecasting/                 # Uncensoring, rolling-origin features, LightGBM quantiles
│   ├── optimization/                # Stochastic safety stock and MILP replenishment solver
│   └── ui/                          # Multipage Streamlit application
├── power_bi/                        # Power BI semantic model blueprint and DAX measures
└── tests/
    ├── unit/                        # Unit tests for domain logic and Pydantic validation
    ├── integration/                 # Pipeline idempotence and quarantine verification
    └── reconciliation/              # 3-way metric reconciliation test suite
```

---

## 4. Quickstart Guide (Windows / PowerShell)

### Prerequisites
- Windows 10/11
- PowerShell 5.1+ or PowerShell 7+
- Python 3.11+ (Python 3.13.7 verified)
- Git 2.40+

### Step 1: Environment Setup
Clone or navigate to the repository, activate the virtual environment, and install dependencies:

```powershell
# Navigate to project directory
cd D:\Documents\Documents\RetailPlus_AI

# Activate existing virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install core dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2: Database Migration & Synthetic Data Ingestion (Phase 3)
```powershell
# Run the end-to-end ingestion and quarantine pipeline
python -m src.data_engine.pipeline --run-all
```

### Step 3: Run Automated Test Suite
```powershell
# Execute all unit, integration, and reconciliation tests
pytest -v
```

### Step 4: Launch the Streamlit Decision Portal
```powershell
# Launch the 4-page interactive web application
streamlit run src/ui/app.py
```

---

## 5. Key Technical Innovations for Interview Defense

1. **Demand Uncensoring Heuristic:**
   - *Question:* "How did you handle stockout periods in your sales history?"
   - *Defense:* "Standard ML models underestimate demand because historical sales drop to zero during stockouts. We implemented an indicator $S_t = \mathbb{I}(I_t = 0)$ and localized rate-of-sale imputation adjusted by day-of-week seasonality factors, preventing the inventory death spiral."

2. **Chronological Rolling-Origin Evaluation:**
   - *Question:* "Why didn't you use standard 5-fold cross-validation?"
   - *Defense:* "Random cross-validation causes catastrophic look-ahead data leakage in time series. We enforced strict walk-forward rolling-origin evaluation where all features rely strictly on information available prior to the forecast horizon ($t \le T$)."

3. **Multi-Item Constrained Replenishment (MILP):**
   - *Question:* "Why not just order the difference between Target Stock and On-Hand?"
   - *Defense:* "Unconstrained replenishment breaches budget ceilings and violates supplier MOQs. We formulated a Mixed-Integer Linear Program in PuLP that minimizes stockout penalty and holding costs subject to discrete pack sizes ($Q_i = k \cdot \text{pack}$), supplier MOQs ($Q_i \ge \text{MOQ} \lor Q_i = 0$), and total working capital budget ($\sum Q_i c_i \le B$)."

4. **3-Way Metric Parity:**
   - *Question:* "How do you ensure the CEO in Power BI sees the exact same margin numbers as your backend SQL database?"
   - *Defense:* "We designed an automated Pytest reconciliation harness that runs the analytical SQL views, the Pandas pipeline, and the DAX measure logic against identical data slices, verifying parity within $\pm 0.01$ tolerance."

---
*Developed with architectural precision for enterprise deployment and academic viva defense.*

