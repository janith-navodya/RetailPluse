"""Unit & Integration Tests for RetailPulse DI CRUD & Data Ingestion Engine."""
import pytest
import pandas as pd
from src.data_engine.crud import (
    get_all_products,
    create_product,
    update_product,
    delete_product,
    get_all_suppliers,
    create_supplier,
    update_supplier,
    delete_supplier,
    adjust_inventory_stock,
    validate_and_import_file,
)


@pytest.mark.database
class TestProductCRUD:
    """Verifies Create, Read, Update, and Delete for Product Catalog."""

    def test_get_all_products_returns_dataframe(self):
        df = get_all_products()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "product_id" in df.columns
        assert "unit_retail_price" in df.columns

    def test_create_product_validation(self):
        # Retail price must exceed cost price
        ok, msg = create_product(
            product_id="PRD_INV",
            product_name="Invalid Item",
            category="Test",
            sub_category="Test",
            brand="Brand",
            supplier_id="SUP01",
            unit_cost_price=10.0,
            unit_retail_price=8.0,  # Invalid: retail < cost
            pack_size=1,
        )
        assert ok is False
        assert "must exceed Cost Price" in msg

    def test_product_lifecycle_roundtrip(self):
        test_pid = "PRD99"
        # 1. Create
        ok, msg = create_product(
            product_id=test_pid,
            product_name="Test Product 99",
            category="Electronics",
            sub_category="Gadgets",
            brand="Acme",
            supplier_id="SUP01",
            unit_cost_price=25.00,
            unit_retail_price=49.99,
            pack_size=6,
            shelf_life_days=365,
        )
        assert ok is True

        # 2. Update
        ok_up, msg_up = update_product(
            product_id=test_pid,
            product_name="Updated Product 99",
            category="Electronics",
            sub_category="Gadgets",
            brand="Acme Pro",
            supplier_id="SUP01",
            unit_cost_price=28.00,
            unit_retail_price=55.00,
            pack_size=12,
        )
        assert ok_up is True

        # 3. Delete
        ok_del, msg_del = delete_product(test_pid, force_cascade=True)
        assert ok_del is True


@pytest.mark.database
class TestSupplierCRUD:
    """Verifies Supplier CRUD operations."""

    def test_get_all_suppliers(self):
        df = get_all_suppliers()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "supplier_id" in df.columns

    def test_supplier_lifecycle(self):
        test_sid = "SUP99"
        # Create
        ok, msg = create_supplier(
            supplier_id=test_sid,
            supplier_name="Test Supplier Logistics",
            contact_email="test@logistics.com",
            mean_lead_time_days=3.5,
            lead_time_std_dev=0.5,
            min_order_qty=20,
        )
        assert ok is True

        # Update
        ok_up, _ = update_supplier(
            supplier_id=test_sid,
            supplier_name="Test Supplier Global",
            contact_email="global@logistics.com",
            mean_lead_time_days=4.0,
            lead_time_std_dev=0.8,
            min_order_qty=30,
            service_level_target_pct=98.0,
        )
        assert ok_up is True

        # Delete
        ok_del, _ = delete_supplier(test_sid)
        assert ok_del is True


@pytest.mark.database
class TestInventoryAdjustment:
    """Verifies live stock adjustments."""

    def test_adjust_inventory_stock(self):
        ok, msg = adjust_inventory_stock(
            store_id="STR01",
            product_id="PRD01",
            new_on_hand_qty=75,
            reason="Physical Audit Test",
        )
        assert ok is True
        assert "Successfully adjusted" in msg


@pytest.mark.database
class TestFileImport:
    """Verifies bulk CSV / Excel validation."""

    def test_import_products_csv(self):
        csv_content = (
            "product_id,product_name,category,sub_category,brand,supplier_id,unit_cost_price,unit_retail_price,pack_size\n"
            "PRD_CSV_1,CSV Item 1,Beverages,Tea,Lipton,SUP01,2.00,3.50,12\n"
            "PRD_CSV_2,CSV Item 2,Beverages,Coffee,Nescafe,SUP01,5.00,8.50,6\n"
        ).encode("utf-8")

        ok, msg, stats = validate_and_import_file(csv_content, "products_test.csv", "Products")
        assert ok is True
        assert stats["imported_rows"] == 2

        # Cleanup
        delete_product("PRD_CSV_1", force_cascade=True)
        delete_product("PRD_CSV_2", force_cascade=True)
