"""Pydantic V2 schemas for strict data validation and constraint enforcement."""
from datetime import date, datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class DimDateSchema(BaseModel):
    date_key: int = Field(..., ge=20200101, le=20351231)
    full_date: date
    day_of_week: int = Field(..., ge=1, le=7)
    day_name: str
    day_of_month: int = Field(..., ge=1, le=31)
    month_num: int = Field(..., ge=1, le=12)
    month_name: str
    quarter: int = Field(..., ge=1, le=4)
    year: int = Field(..., ge=2020, le=2035)
    is_weekend: int = Field(..., ge=0, le=1)
    is_holiday: int = Field(..., ge=0, le=1)


class DimStoreSchema(BaseModel):
    store_id: str = Field(..., min_length=2, max_length=10)
    store_name: str
    store_format: Literal["Flagship Urban", "Suburban Superstore", "Express"]
    city: str
    state: str
    square_footage: int = Field(..., gt=0)
    storage_capacity_units: int = Field(..., gt=0)


class DimSupplierSchema(BaseModel):
    supplier_id: str = Field(..., min_length=2, max_length=10)
    supplier_name: str
    contact_email: str
    mean_lead_time_days: float = Field(..., ge=1.0)
    lead_time_std_dev: float = Field(..., ge=0.0)
    min_order_qty: int = Field(..., ge=1)
    service_level_target_pct: float = Field(..., ge=50.0, le=99.9)


class DimProductSchema(BaseModel):
    product_id: str = Field(..., min_length=2, max_length=10)
    product_name: str
    category: str
    sub_category: str
    brand: str
    supplier_id: str
    unit_cost_price: float = Field(..., gt=0.0)
    unit_retail_price: float = Field(..., gt=0.0)
    pack_size: int = Field(..., ge=1)
    shelf_life_days: Optional[int] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_retail_exceeds_cost(self):
        if self.unit_retail_price <= self.unit_cost_price:
            raise ValueError(
                f"unit_retail_price ({self.unit_retail_price}) must exceed unit_cost_price ({self.unit_cost_price})"
            )
        return self


class FactSalesDailySchema(BaseModel):
    date_key: int = Field(..., ge=20200101, le=20351231)
    store_id: str
    product_id: str
    quantity_sold: int = Field(..., ge=0)
    gross_sales_amount: float = Field(..., ge=0.0)
    discount_amount: float = Field(..., ge=0.0)
    net_sales_amount: float = Field(..., ge=0.0)
    cogs_amount: float = Field(..., ge=0.0)
    gross_profit_amount: float
    is_promotional: int = Field(..., ge=0, le=1)
    batch_id: str
    ingested_at: datetime

    @model_validator(mode="after")
    def validate_financial_consistency(self):
        expected_net = round(self.gross_sales_amount - self.discount_amount, 2)
        if abs(self.net_sales_amount - expected_net) > 0.05:
            raise ValueError(
                f"net_sales_amount ({self.net_sales_amount}) != gross ({self.gross_sales_amount}) - discount ({self.discount_amount})"
            )
        expected_profit = round(self.net_sales_amount - self.cogs_amount, 2)
        if abs(self.gross_profit_amount - expected_profit) > 0.05:
            raise ValueError(
                f"gross_profit_amount ({self.gross_profit_amount}) != net_sales ({self.net_sales_amount}) - cogs ({self.cogs_amount})"
            )
        return self


class FactInventorySnapshotSchema(BaseModel):
    date_key: int = Field(..., ge=20200101, le=20351231)
    store_id: str
    product_id: str
    beginning_on_hand_qty: int = Field(..., ge=0)
    received_qty: int = Field(..., ge=0)
    sold_qty: int = Field(..., ge=0)
    ending_on_hand_qty: int = Field(..., ge=0)
    ending_inventory_value: float = Field(..., ge=0.0)
    is_stockout: int = Field(..., ge=0, le=1)
    batch_id: str
    ingested_at: datetime

    @model_validator(mode="after")
    def validate_inventory_physics(self):
        expected_ending = self.beginning_on_hand_qty + self.received_qty - self.sold_qty
        if self.ending_on_hand_qty != expected_ending:
            raise ValueError(
                f"Physical balance violation: ending_on_hand ({self.ending_on_hand_qty}) != "
                f"beginning ({self.beginning_on_hand_qty}) + received ({self.received_qty}) - sold ({self.sold_qty})"
            )
        expected_stockout = 1 if self.ending_on_hand_qty == 0 else 0
        if self.is_stockout != expected_stockout:
            raise ValueError(
                f"Stockout flag mismatch: is_stockout is {self.is_stockout}, expected {expected_stockout}"
            )
        return self


class FactPurchaseOrderSchema(BaseModel):
    po_id: str = Field(..., min_length=5, max_length=30)
    order_date_key: int = Field(..., ge=20200101, le=20351231)
    expected_delivery_date_key: int = Field(..., ge=20200101, le=20351231)
    actual_delivery_date_key: Optional[int] = Field(default=None, ge=20200101, le=20351231)
    store_id: str
    product_id: str
    supplier_id: str
    order_qty: int = Field(..., gt=0)
    received_qty: int = Field(..., ge=0)
    unit_cost_price: float = Field(..., gt=0.0)
    total_cost_amount: float = Field(..., gt=0.0)
    status: Literal["PLACED", "IN_TRANSIT", "DELIVERED", "CANCELLED"]
    batch_id: str
    ingested_at: datetime

