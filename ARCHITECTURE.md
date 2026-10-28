# RETAILPULSE DECISION INTELLIGENCE (DI)
## SYSTEM ARCHITECTURE SPECIFICATION & CLEAN ARCHITECTURE DESIGN

---

### 1. Architectural Philosophy: Clean Architecture

The RetailPulse DI platform is organized according to the principles of **Clean Architecture** (Uncle Bob Martin). Business rules and domain models sit at the center, completely isolated from databases, machine learning frameworks, and user interfaces.

```
 +---------------------------------------------------------------+
 |                        Presentation                           |
 |      Streamlit Dashboard (Pages 1-4)  |  Power BI (.pbix)     |
 +-------------------------------+-------------------------------+
                                 |
                                 v
 +---------------------------------------------------------------+
 |                   Application / Pipeline Core                 |
 |  Forecasting (LightGBM) | Optimization (PuLP) | Analytics     |
 +-------------------------------+-------------------------------+
                                 |
                                 v
 +---------------------------------------------------------------+
 |                     Data Engine & Adapters                    |
 | Pydantic Validators | Quarantine Dead-Letter | SQLAlchemy DB  |
 +-------------------------------+-------------------------------+
                                 |
                                 v
 +---------------------------------------------------------------+
 |                     Enterprise Domain Core                    |
 |   Entities (Product, Store) | Value Objects (Currency, DoS)   |
 +---------------------------------------------------------------+
```

#### Layer Dependency Rule:
Source code dependencies point inward only.
1. **Domain Layer (`src/domain/`):** Contains immutable dataclasses, mathematical definitions (Safety Stock, ROP, Pack Size rounding), and domain invariants. Zero third-party library dependencies (no Pandas, no LightGBM, pure Python).
2. **Data Engine Layer (`src/data_engine/`):** Manages data ingestion, Pydantic type validation, quarantine routing of invalid rows, and idempotent database loading.
3. **Analytics & BI Core (`src/analytics/`):** Houses SQL view execution, Python metric calculation, and the 3-way reconciliation harness (SQL vs. Python vs. DAX).
4. **Forecasting Engine (`src/forecasting/`):** Manages demand uncensoring heuristics, rolling-origin chronological feature engineering (strictly zero leakage), baselines, and LightGBM quantile regressors ($P_{10}, P_{50}, P_{90}$).
5. **Optimization Engine (`src/optimization/`):** Solves the multi-item replenishment linear program via PuLP, subject to supplier MOQs, discrete pack sizes, and total working capital budget.
6. **Presentation Layer (`src/ui/` & `power_bi/`):** Streamlit operational cockpit and Power BI DAX semantic model blueprint.

---

### 2. End-to-End Component Interfaces

#### A. Ingestion & Validation Pipeline
```
[Raw CSV / JSON Feeds]
          │
          ▼
┌─────────────────────────┐
│ IngestionValidator      │
│ (Pydantic Schema Check) │
└───────────┬─────────────┘
            │
      ┌─────┴───────────────────────┐
      │ Valid                       │ Invalid
      ▼                             ▼
┌─────────────────────────┐   ┌───────────────────────────┐
│ Idempotent Database     │   │ Quarantine Table          │
│ Upsert Engine           │   │ (Dead-Letter JSON Audit)  │
│ (fact_*, dim_*)         │   │ (quarantine_invalid_recs) │
└─────────────────────────┘   └───────────────────────────┘
```
- **Inputs:** Raw data records (dict / DataFrame / CSV).
- **Interface Contract:**
  ```python
  class IngestionPipeline:
      def run(self, source_feed: str, raw_df: pd.DataFrame, batch_id: str) -> IngestionSummary:
          """
          Validates records against Pydantic schema.
          Valid records -> committed to DB with batch_id.
          Invalid records -> written to quarantine_invalid_records with error trace.
          Returns IngestionSummary(processed, loaded, quarantined).
          """
  ```

#### B. Demand Uncensoring Module
- **Problem:** Historical sales $Y_t = \min(D_t, I_t)$. When $I_t = 0$, $Y_t = 0$ masks true demand.
- **Interface Contract:**
  ```python
  class DemandUncensoringEngine:
      def uncensor(self, sales_df: pd.DataFrame, inventory_df: pd.DataFrame) -> pd.DataFrame:
          """
          Flags stockout periods where ending_on_hand == 0.
          Applies rate-of-sale moving average adjusted for day-of-week seasonality.
          Returns augmented DataFrame with columns: [is_censored, imputed_demand].
          """
  ```

#### C. Rolling-Origin Feature Engineering & Forecaster
- **Chronological Guarantee:** No random k-fold cross-validation. All features use strictly trailing lag windows ($\tau \le t$).
- **Features Generated:**
  - Lags: $t-1, t-2, t-7, t-14, t-28$
  - Rolling Stats: 7-day and 28-day rolling mean, rolling standard deviation
  - Calendar: Day of week, Month, Is Weekend, Is Promotional Event
- **Interface Contract:**
  ```python
  class QuantileForecaster:
      def fit(self, X_train: pd.DataFrame, y_train: pd.Series) -> None: ...
      def predict_quantiles(self, X_future: pd.DataFrame) -> Dict[str, np.ndarray]:
          """
          Returns {'P10': array, 'P50': array, 'P90': array}
          representing 10th, 50th, and 90th percentile demand forecasts.
          """
  ```

#### D. Constrained Replenishment Optimizer
- **Formulation:**
  - Let $i \in \{1, \dots, N\}$ index products.
  - Let $Q_i$ be the order quantity.
  - Let $c_i$ be unit cost, $m_i$ be supplier MOQ, $p_i$ be pack size.
  - Let $k_i \in \mathbb{Z}_{\ge 0}$ be the number of packs ordered: $Q_i = k_i \cdot p_i$.
  - Objective: Minimize expected economic loss (Unsatisfied Demand Penalty + Inventory Holding Cost):
    $$\min \sum_{i} \left[ h_i \cdot \max(0, I_{0,i} + Q_i - D_{90,i}) + \pi_i \cdot \max(0, D_{50,i} - I_{0,i} - Q_i) \right]$$
  - Subject to:
    $$\sum_{i} Q_i \cdot c_i \le B \quad (\text{Working Capital Budget})$$
    $$Q_i \ge m_i \quad \text{or} \quad Q_i = 0 \quad (\text{Supplier MOQ})$$
    $$Q_i = k_i \cdot p_i, \quad k_i \in \{0, 1, 2, \dots\} \quad (\text{Discrete Pack Sizes})$$
- **Interface Contract:**
  ```python
  class ReplenishmentOptimizer:
      def solve(
          self, 
          candidates: List[ReplenishmentCandidate], 
          total_budget: float
      ) -> OptimizationResult:
          """
          Formulates Mixed-Integer Linear Program (MILP) in PuLP.
          Returns approved purchase orders, budget allocated, and expected stockout reduction.
          """
  ```

---

### 3. Database Persistence & Repository Pattern

To ensure 100% testability and zero-dependency local operation, database interaction utilizes the **SQLAlchemy 2.0 Repository Pattern**:

```python
class DatabaseSessionManager:
    def __init__(self, connection_url: str):
        self.engine = create_engine(connection_url, echo=False)
        self.session_factory = sessionmaker(bind=self.engine)

    def get_session(self) -> Session: ...
```

- **Default Engine:** `sqlite:///data/retailpulse.db` (zero external daemon, instant local execution, fully ACID-compliant).
- **Enterprise Extensibility:** Seamlessly switches to Microsoft SQL Server (`mssql+pyodbc://...`) or PostgreSQL (`postgresql+psycopg2://...`) without changing a single line of business logic.

---

### 4. System Sequence: End-to-End Decision Flow

```mermaid
sequenceDiagram
    autonumber
    actor Planner as Inventory Analyst
    participant UI as Streamlit UI
    participant Pipeline as Ingestion Engine
    participant DB as SQLite / Star Schema
    participant ML as Forecaster (LightGBM)
    participant Opt as Replenishment Solver (PuLP)

    Note over Pipeline, DB: Step 1: Ingestion & Quarantine
    Pipeline->>Pipeline: Validate raw data vs. Pydantic
    Pipeline->>DB: Upsert valid records (fact_*, dim_*)
    Pipeline->>DB: Log invalid records (quarantine_invalid_records)

    Note over UI, ML: Step 2: Forecast Generation
    Planner->>UI: Select Store & Review Horizon
    UI->>DB: Query historical sales & stockout flags
    DB-->>UI: Return historical time-series
    UI->>ML: Trigger Rolling-Origin Forecast
    ML->>ML: Heuristic Demand Uncensoring
    ML->>ML: Generate P10, P50, P90 Quantiles
    ML-->>UI: Render Forecast Cone

    Note over UI, Opt: Step 3: Constrained Optimization
    Planner->>UI: Set Available Budget ($) & Service Target
    UI->>Opt: Submit Candidates, Current Stock, MOQs, Pack Sizes
    Opt->>Opt: Solve MILP (PuLP)
    Opt-->>UI: Return Recommended Purchase Orders
    Planner->>UI: Accept / Modify / Export PO Batch
    UI->>DB: Commit Approved POs to fact_purchase_orders
```

---

### 5. Test Strategy & Verification Matrix

Quality engineering is embedded across four distinct testing rings:

```
          ┌──────────────────────────────────────┐
          │      UI & E2E Smoke Tests            │
          │   Streamlit page render verification │
          ├──────────────────────────────────────┤
          │   Reconciliation Test Harness        │
          │   SQL vs. Python vs. DAX parity      │
          ├──────────────────────────────────────┤
          │       Integration Tests              │
          │   ETL Idempotence & Quarantine Audit │
          ├──────────────────────────────────────┤
          │          Unit Tests                  │
          │   Domain math, Pydantic, Safety Stock│
          └──────────────────────────────────────┘
```

1. **Unit Tests (`tests/unit/`):**
   - Pure domain tests: Safety stock formula ($Z \cdot \sigma$), ROP formula, discrete pack size quantization.
   - Pydantic schema rejection for negative prices, invalid dates, and invalid category values.
   - Uncensoring heuristic edge cases (100% stockout, 0% stockout).
2. **Integration Tests (`tests/integration/`):**
   - Ingestion idempotence: Ingesting the same batch twice produces zero duplicate rows in fact tables.
   - Quarantine routing: Malformed records are correctly filtered into `quarantine_invalid_records` while clean records proceed to `fact_sales_daily`.
   - Linear program feasibility under extreme budget constraints ($B = 0$, $B = \$100$, $B \to \infty$).
3. **Reconciliation Tests (`tests/reconciliation/`):**
   - 3-Way metric reconciliation for Net Sales, COGS, Gross Profit, Gross Margin %, DoS, Stockout Rate, and Inventory Turnover within $\pm 0.01$ tolerance.

---
*Document Version: 1.0.0*  
*Author: RetailPulse Architecture Team*
