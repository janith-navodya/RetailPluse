"""Decision Persistence & Approval Workflow Engine for RetailPulse DI Platform.

Persists MILP replenishment recommendations into Microsoft SQL Server table
dbo.fact_replenishment_recommendation and manages human-in-the-loop approval workflows:
PROPOSED -> APPROVED / MODIFIED / REJECTED.
"""
import uuid
import warnings
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import pyodbc
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

from config.settings import settings
from config.logging_config import logger
from src.decision.optimizer import ReplenishmentOrderRecommendation


class ReplenishmentPersistenceEngine:
    """Manages database persistence and approval state transitions for order recommendations."""

    def __init__(self, db_name: str = settings.DB_NAME):
        self.db_name = db_name
        self.conn_str = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            "SERVER=localhost;"
            f"DATABASE={self.db_name};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )

    def get_connection(self) -> pyodbc.Connection:
        return pyodbc.connect(self.conn_str)

    def persist_recommendations(
        self,
        recommendations: List[ReplenishmentOrderRecommendation],
        run_date_key: int,
        batch_id: Optional[str] = None,
    ) -> int:
        """
        Idempotently saves replenishment recommendations to SQL Server.
        Deletes prior PROPOSED recommendations for this run_date_key before inserting fresh batch.
        """
        if not recommendations:
            return 0

        if batch_id is None:
            batch_id = f"REPL-{uuid.uuid4().hex[:10].upper()}"

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.fast_executemany = True

        # Idempotent cleanup: remove any existing recommendations for this run_date_key
        cursor.execute(
            "DELETE FROM dbo.fact_replenishment_recommendation WHERE run_date_key = ?;",
            (run_date_key,),
        )
        conn.commit()

        insert_sql = """
            INSERT INTO dbo.fact_replenishment_recommendation (
                recommendation_id, run_date_key, store_id, product_id, supplier_id,
                current_on_hand_qty, current_on_order_qty, inventory_position,
                lead_time_demand_qty, safety_stock_qty, reorder_point_qty,
                inventory_status, recommended_units, recommended_packs,
                unit_cost_price, estimated_cost, priority_rank, approval_status,
                batch_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PROPOSED', ?, ?);
        """

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        params = []
        for r in recommendations:
            rec_id = f"REC-{run_date_key}-{r.store_id}-{r.product_id}"
            params.append(
                (
                    rec_id,
                    run_date_key,
                    r.store_id,
                    r.product_id,
                    r.supplier_id,
                    r.current_on_hand_qty,
                    r.current_on_order_qty,
                    r.inventory_position,
                    r.lead_time_demand_qty,
                    r.safety_stock_qty,
                    r.reorder_point_qty,
                    r.inventory_status,
                    r.recommended_units,
                    r.recommended_packs,
                    r.unit_cost_price,
                    r.estimated_cost,
                    r.priority_rank,
                    batch_id,
                    now_str,
                )
            )

        cursor.executemany(insert_sql, params)
        conn.commit()
        conn.close()

        logger.info(
            "Persisted %d replenishment recommendations to dbo.fact_replenishment_recommendation for date %d (Batch: %s).",
            len(recommendations),
            run_date_key,
            batch_id,
        )
        return len(recommendations)

    def update_recommendation_status(
        self,
        recommendation_id: str,
        new_status: str,
        modified_units: Optional[int] = None,
    ) -> bool:
        """Transitions approval state between PROPOSED, APPROVED, MODIFIED, REJECTED."""
        valid_statuses = {"PROPOSED", "APPROVED", "MODIFIED", "REJECTED"}
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid approval status: {new_status}. Allowed: {valid_statuses}")

        conn = self.get_connection()
        cursor = conn.cursor()

        if new_status == "MODIFIED" and modified_units is not None:
            cursor.execute(
                """
                UPDATE dbo.fact_replenishment_recommendation
                SET approval_status = ?, recommended_units = ?, estimated_cost = ? * unit_cost_price
                WHERE recommendation_id = ?;
                """,
                (new_status, modified_units, modified_units, recommendation_id),
            )
        else:
            cursor.execute(
                """
                UPDATE dbo.fact_replenishment_recommendation
                SET approval_status = ?
                WHERE recommendation_id = ?;
                """,
                (new_status, recommendation_id),
            )

        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

    def query_recommendations(
        self,
        run_date_key: Optional[int] = None,
        store_id: Optional[str] = None,
        approval_status: Optional[str] = None,
    ) -> pd.DataFrame:
        """Retrieves stored recommendations with optional filters."""
        conn = self.get_connection()
        query = "SELECT * FROM dbo.fact_replenishment_recommendation WHERE 1=1"
        params = []
        if run_date_key:
            query += " AND run_date_key = ?"
            params.append(run_date_key)
        if store_id:
            query += " AND store_id = ?"
            params.append(store_id)
        if approval_status:
            query += " AND approval_status = ?"
            params.append(approval_status)

        query += " ORDER BY priority_rank ASC;"
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        return df
