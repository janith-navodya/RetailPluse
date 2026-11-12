"""Page: Enterprise Data Hub & Master File Operations (Input, Edit, Delete, Bulk Upload)."""
from __future__ import annotations

import io
import sys
import importlib
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure in-memory modules are kept in sync with disk for hot-reloading Streamlit sessions
for _mod in ("src.data_engine.crud", "src.ui.data_access"):
    if _mod in sys.modules:
        try:
            importlib.reload(sys.modules[_mod])
        except Exception:
            pass

import streamlit as st
import pandas as pd

from src.ui.styles import apply_custom_styles, render_header, render_metric_card
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
from src.ui.data_access import get_latest_inventory_health

try:
    st.set_page_config(page_title="Data Hub | RetailPulse DI", page_icon="📁", layout="wide")
except Exception:
    pass

apply_custom_styles()

render_header(
    title="Master Data Hub & Records Manager",
    subtitle="Direct interactive Input, Edit, Delete, and Bulk File Ingestion for enterprise products, suppliers, and inventory positions.",
    badge="Master Data CRUD",
)

tab_products, tab_suppliers, tab_stock, tab_files = st.tabs([
    "🏷️ Products Manager",
    "🏭 Suppliers Directory",
    "📦 Inventory Stock Adjustments",
    "📤 Bulk CSV / Excel Importer",
])

# ==============================================================================
# TAB 1: Products Manager (CRUD)
# ==============================================================================
with tab_products:
    st.markdown("### 🏷️ Product Catalog Management")
    st.caption("Inspect, create, edit prices, or remove products in Microsoft SQL Server (`dbo.dim_product`).")

    df_prods = get_all_products()

    if df_prods.empty:
        st.warning("No products found in database.")
    else:
        # Quick KPI Banner
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_metric_card("Total Products", f"{len(df_prods)} SKUs")
        with c2:
            num_cats = df_prods["category"].nunique()
            render_metric_card("Merchandise Categories", f"{num_cats} Categories")
        with c3:
            avg_margin = (df_prods["unit_retail_price"] - df_prods["unit_cost_price"]).mean()
            render_metric_card("Avg Unit Margin", f"${avg_margin:,.2f}")
        with c4:
            avg_retail = df_prods["unit_retail_price"].mean()
            render_metric_card("Avg Retail Price", f"${avg_retail:,.2f}")

        st.markdown("<br>", unsafe_allow_html=True)

        # Action Bar: Add Product & Delete Product Forms
        col_act1, col_act2 = st.columns([1, 1])

        with col_act1:
            with st.expander("➕ **Add New Product (Input)**", expanded=False):
                with st.form("form_add_product", clear_on_submit=True):
                    f_c1, f_c2 = st.columns(2)
                    with f_c1:
                        new_pid = st.text_input("Product ID (Max 10 Chars)*", placeholder="e.g. PRD51").upper()
                        new_pname = st.text_input("Product Name*", placeholder="e.g. Organic Almond Milk 1L")
                        new_cat = st.selectbox("Category*", options=sorted(df_prods["category"].unique().tolist()))
                        new_subcat = st.text_input("Sub-Category", value="General")
                        new_brand = st.text_input("Brand", value="RetailPulse")
                    with f_c2:
                        df_sups = get_all_suppliers()
                        sup_choices = df_sups["supplier_id"].tolist() if not df_sups.empty else ["SUP01"]
                        new_sup = st.selectbox("Supplier ID*", options=sup_choices)
                        new_cost = st.number_input("Unit Cost Price ($)*", min_value=0.10, max_value=5000.0, value=5.00, step=0.50)
                        new_retail = st.number_input("Unit Retail Price ($)*", min_value=0.20, max_value=10000.0, value=9.99, step=0.50)
                        new_pack = st.number_input("Pack Size (Units)*", min_value=1, max_value=500, value=6, step=1)
                        new_shelf = st.number_input("Shelf Life (Days, Optional)", min_value=0, max_value=1000, value=30, step=5)

                    submitted = st.form_submit_button("✅ Create Product in Database", type="primary", width='stretch')
                    if submitted:
                        ok, msg = create_product(
                            product_id=new_pid,
                            product_name=new_pname,
                            category=new_cat,
                            sub_category=new_subcat,
                            brand=new_brand,
                            supplier_id=new_sup,
                            unit_cost_price=new_cost,
                            unit_retail_price=new_retail,
                            pack_size=new_pack,
                            shelf_life_days=new_shelf if new_shelf > 0 else None,
                        )
                        if ok:
                            st.toast(f"✅ {msg}")
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        with col_act2:
            with st.expander("🗑️ **Delete / Archive Product**", expanded=False):
                st.caption("Safely remove obsolete SKUs from the master catalog.")
                del_cat_filter = st.selectbox(
                    "Filter by Category (Optional)",
                    options=["All Categories"] + sorted(df_prods["category"].dropna().unique().tolist()),
                    key="del_cat_filter_opt",
                )
                df_del_pool = df_prods if del_cat_filter == "All Categories" else df_prods[df_prods["category"] == del_cat_filter]
                if df_del_pool.empty:
                    st.info("No products match the selected category.")
                else:
                    del_pid = st.selectbox(
                        "Select Product to Delete",
                        options=df_del_pool["product_id"].tolist(),
                        format_func=lambda x: f"{x} — {df_del_pool.loc[df_del_pool['product_id']==x, 'product_name'].iloc[0]}",
                        key="del_pid_select",
                    )
                    force_del = st.checkbox("Cascade Delete (removes linked historical records)", value=False)
                    if st.button("🚨 Confirm Product Deletion", type="secondary", width='stretch'):
                        ok, msg = delete_product(del_pid, force_cascade=force_del)
                        if ok:
                            st.toast(f"🗑️ {msg}")
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        # Interactive Data Editor (Edit)
        st.markdown("#### ✏️ Interactive Catalog Editor (Double-Click Any Cell to Edit)")
        st.caption("Modify product details directly in the grid. Click 'Save Inline Edits' below to persist changes to SQL Server.")

        # Search and Category Filter Toolbar
        f_c1, f_c2 = st.columns([2, 1])
        with f_c1:
            prod_search = st.text_input(
                "🔍 Search Products (SKU, Name, or Brand)",
                placeholder="e.g. PRD60, Pen, Dairy, Produce...",
                key="prod_catalog_search",
            )
        with f_c2:
            cat_list = ["All Categories"] + sorted(df_prods["category"].dropna().unique().tolist())
            prod_cat_filter = st.selectbox("Filter Catalog by Category", options=cat_list, key="prod_catalog_cat")

        view_prods = df_prods.copy()
        if prod_cat_filter != "All Categories":
            view_prods = view_prods[view_prods["category"] == prod_cat_filter]
        if prod_search.strip():
            s = prod_search.strip().lower()
            view_prods = view_prods[
                view_prods["product_id"].astype(str).str.lower().str.contains(s)
                | view_prods["product_name"].astype(str).str.lower().str.contains(s)
                | view_prods["brand"].astype(str).str.lower().str.contains(s)
            ]

        st.caption(f"Displaying **{len(view_prods)}** of **{len(df_prods)}** catalog items.")

        edited_df = st.data_editor(
            view_prods,
            column_config={
                "product_id": st.column_config.TextColumn("SKU ID", disabled=True),
                "product_name": st.column_config.TextColumn("Product Name", required=True),
                "category": st.column_config.TextColumn("Category"),
                "sub_category": st.column_config.TextColumn("Sub-Category"),
                "brand": st.column_config.TextColumn("Brand"),
                "supplier_id": st.column_config.TextColumn("Supplier ID"),
                "unit_cost_price": st.column_config.NumberColumn("Cost Price ($)", format="$%.2f", min_value=0.01),
                "unit_retail_price": st.column_config.NumberColumn("Retail Price ($)", format="$%.2f", min_value=0.01),
                "pack_size": st.column_config.NumberColumn("Pack Size", min_value=1),
                "shelf_life_days": st.column_config.NumberColumn("Shelf Life (Days)"),
            },
            hide_index=True,
            width='stretch',
            height=380,
            key="product_catalog_editor",
        )

        if st.button("💾 Save All Inline Edits to SQL Server", type="primary"):
            updated_count = 0
            errs = []
            for _, row in edited_df.iterrows():
                ok, msg = update_product(
                    product_id=str(row["product_id"]),
                    product_name=str(row["product_name"]),
                    category=str(row["category"]),
                    sub_category=str(row["sub_category"]),
                    brand=str(row["brand"]),
                    supplier_id=str(row["supplier_id"]),
                    unit_cost_price=float(row["unit_cost_price"]),
                    unit_retail_price=float(row["unit_retail_price"]),
                    pack_size=int(row["pack_size"]),
                    shelf_life_days=int(row["shelf_life_days"]) if pd.notna(row["shelf_life_days"]) else None,
                )
                if ok:
                    updated_count += 1
                else:
                    errs.append(f"{row['product_id']}: {msg}")

            if errs:
                st.warning(f"Saved {updated_count} products. Encountered issues: {'; '.join(errs)}")
            else:
                st.toast(f"💾 Successfully updated {updated_count} products in SQL Server!")
                st.success(f"All {updated_count} products successfully synchronized with database.")
                st.rerun()

# ==============================================================================
# TAB 2: Suppliers Directory (CRUD)
# ==============================================================================
with tab_suppliers:
    st.markdown("### 🏭 Supplier Directory Management")
    st.caption("Manage procurement partners, delivery lead times, and minimum order quantity (MOQ) contracts.")

    df_sups = get_all_suppliers()

    s_col1, s_col2 = st.columns([1, 1])

    with s_col1:
        with st.expander("➕ **Register New Supplier (Input)**", expanded=False):
            with st.form("form_add_supplier", clear_on_submit=True):
                new_sid = st.text_input("Supplier ID (Max 10 Chars)*", placeholder="e.g. SUP11").upper()
                new_sname = st.text_input("Supplier Business Name*", placeholder="e.g. Apex Global Distributors")
                new_email = st.text_input("Procurement Email*", placeholder="e.g. orders@apex.com")
                c_s1, c_s2 = st.columns(2)
                with c_s1:
                    new_mean_lt = st.number_input("Mean Lead Time (Days)*", min_value=1.0, max_value=60.0, value=3.0, step=0.5)
                    new_std_lt = st.number_input("Lead Time Std Dev (Days)", min_value=0.0, max_value=15.0, value=0.5, step=0.1)
                with c_s2:
                    new_moq = st.number_input("Minimum Order Qty (MOQ)*", min_value=1, max_value=5000, value=24, step=6)
                    new_csl = st.number_input("Target Service Level (%)", min_value=50.0, max_value=99.9, value=95.0, step=1.0)

                sup_submitted = st.form_submit_button("✅ Register Supplier", type="primary", width='stretch')
                if sup_submitted:
                    ok, msg = create_supplier(
                        supplier_id=new_sid,
                        supplier_name=new_sname,
                        contact_email=new_email,
                        mean_lead_time_days=new_mean_lt,
                        lead_time_std_dev=new_std_lt,
                        min_order_qty=new_moq,
                        service_level_target_pct=new_csl,
                    )
                    if ok:
                        st.toast(f"✅ {msg}")
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    with s_col2:
        with st.expander("🗑️ **Delete Supplier**", expanded=False):
            st.caption("Remove inactive suppliers (only allowed if no products are linked).")
            del_sid = st.selectbox("Select Supplier to Delete", options=df_sups["supplier_id"].tolist(), format_func=lambda x: f"{x} - {df_sups.loc[df_sups['supplier_id']==x, 'supplier_name'].iloc[0]}")
            if st.button("🚨 Delete Supplier", type="secondary", width='stretch'):
                ok, msg = delete_supplier(del_sid)
                if ok:
                    st.toast(f"🗑️ {msg}")
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    st.markdown("#### 📋 Registered Procurement Partners")
    st.dataframe(
        df_sups.style.format({
            "mean_lead_time_days": "{:.1f} days",
            "lead_time_std_dev": "{:.2f}",
            "min_order_qty": "{:,} units",
            "service_level_target_pct": "{:.1f}%",
        }),
        width='stretch',
        height=320,
    )

# ==============================================================================
# TAB 3: Inventory Stock Adjustments (Physical Audit Corrections)
# ==============================================================================
with tab_stock:
    st.markdown("### 📦 Live Inventory Stock Adjustments")
    st.caption(
        "Execute physical count adjustments, initial stock loads, or audit reconciliations. "
        "Immediately updates `fact_inventory_snapshot` and recalculates inventory valuation in SQL Server."
    )

    df_all_prods = get_all_products()
    df_inv = get_latest_inventory_health()

    if df_all_prods.empty:
        st.warning("No products found in the catalog. Please add products in the Products Manager tab first.")
    else:
        # Build store metadata directly from inventory health or standard locations
        fallback_stores = {
            "STR01": "Downtown Metro Flagship",
            "STR02": "Suburban Mega Center",
            "STR03": "Westside QuickMart",
        }
        if not df_inv.empty and "store_id" in df_inv.columns:
            store_opts = sorted(df_inv["store_id"].unique().tolist())
            if "store_name" in df_inv.columns:
                store_labels = dict(zip(df_inv["store_id"], df_inv["store_name"]))
            else:
                store_labels = fallback_stores
        else:
            store_opts = list(fallback_stores.keys())
            store_labels = fallback_stores

        # 1. Location & SKU Filtering Bar
        f_loc1, f_loc2, f_loc3 = st.columns([1.2, 1, 1.5])

        with f_loc1:
            adj_store = st.selectbox(
                "🏢 Store Location",
                options=store_opts,
                format_func=lambda s: f"{s} — {store_labels.get(s, s)}",
                key="adj_store_select",
            )

        with f_loc2:
            cat_opts = ["All Categories"] + sorted(df_all_prods["category"].dropna().unique().tolist())
            adj_cat = st.selectbox("📂 Filter Category", options=cat_opts, key="adj_cat_filter")

        with f_loc3:
            adj_search = st.text_input(
                "🔍 Quick Search SKU / Name",
                placeholder="e.g. PRD60, Pen, Produce, Milk...",
                key="adj_search_box",
            )

        # Filter products list based on category & search text
        eligible_prods = df_all_prods.copy()
        if adj_cat != "All Categories":
            eligible_prods = eligible_prods[eligible_prods["category"] == adj_cat]
        if adj_search.strip():
            s_q = adj_search.strip().lower()
            eligible_prods = eligible_prods[
                eligible_prods["product_id"].astype(str).str.lower().str.contains(s_q)
                | eligible_prods["product_name"].astype(str).str.lower().str.contains(s_q)
                | eligible_prods["brand"].astype(str).str.lower().str.contains(s_q)
            ]

        if eligible_prods.empty:
            st.info(f"No products found matching '{adj_search}'. Showing all available catalog products.")
            eligible_prods = df_all_prods.copy()

        # Map current store stock levels from inventory health snapshot
        store_snapshots = df_inv[df_inv["store_id"] == adj_store] if not df_inv.empty else pd.DataFrame()
        stock_lookup = {}
        dos_lookup = {}
        vel_lookup = {}
        if not store_snapshots.empty:
            for _, r in store_snapshots.iterrows():
                stock_lookup[str(r["product_id"])] = int(r["closing_stock_on_hand"])
                dos_lookup[str(r["product_id"])] = float(r["days_of_supply"])
                vel_lookup[str(r["product_id"])] = float(r["rolling_30d_avg_daily_sales"])

        # Format product choices with instant on-hand stock visibility
        def format_product_option(pid: str) -> str:
            p_name = eligible_prods.loc[eligible_prods["product_id"] == pid, "product_name"].iloc[0]
            qty = stock_lookup.get(pid, 0)
            tag = "🔴 OUT OF STOCK (0 units)" if qty == 0 else f"✅ {qty:,} units on hand"
            return f"{pid} — {p_name} [{tag}]"

        st.markdown("<br>", unsafe_allow_html=True)
        adj_col1, adj_col2 = st.columns([1.1, 1])

        with adj_col1:
            st.markdown("##### 📦 Select Target Product")
            adj_prod = st.selectbox(
                f"Choose from {len(eligible_prods)} Filtered Products",
                options=eligible_prods["product_id"].tolist(),
                format_func=format_product_option,
                key="adj_prod_select",
            )

            # Metadata details for selected product
            sel_row = eligible_prods[eligible_prods["product_id"] == adj_prod].iloc[0]
            curr_stock = stock_lookup.get(adj_prod, 0)
            cost_val = float(sel_row["unit_cost_price"])
            retail_val = float(sel_row["unit_retail_price"])
            curr_val = curr_stock * cost_val
            curr_dos = dos_lookup.get(adj_prod, 0.0)
            curr_vel = vel_lookup.get(adj_prod, 0.0)

            # Informative Product Card
            st.markdown(
                f"""
                <div style="background-color: #0F172A; border: 1px solid #1E293B; border-radius: 8px; padding: 14px 18px; margin-top: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: baseline;">
                        <span style="font-weight: 700; font-size: 1.15rem; color: #F8FAFC;">{sel_row['product_id']}: {sel_row['product_name']}</span>
                        <span style="font-size: 0.8rem; background: {'#EF4444' if curr_stock == 0 else '#10B981'}; color: #FFFFFF; font-weight: 700; padding: 2px 8px; border-radius: 4px;">
                            {'OUT OF STOCK' if curr_stock == 0 else f'{curr_stock:,} UNITS'}
                        </span>
                    </div>
                    <div style="color: #94A3B8; font-size: 0.85rem; margin-top: 4px;">
                        Category: <strong style="color: #E2E8F0;">{sel_row['category']}</strong> | 
                        Brand: <strong style="color: #E2E8F0;">{sel_row['brand']}</strong> | 
                        Pack Size: <strong style="color: #E2E8F0;">{sel_row['pack_size']} units</strong>
                    </div>
                    <div style="border-top: 1px solid #1E293B; margin-top: 10px; padding-top: 10px; display: flex; justify-content: space-between; font-size: 0.85rem;">
                        <span>Unit Cost: <strong style="color: #38BDF8;">${cost_val:.2f}</strong></span>
                        <span>Unit Retail: <strong style="color: #38BDF8;">${retail_val:.2f}</strong></span>
                        <span>Current Value: <strong style="color: #F8FAFC;">${curr_val:,.2f}</strong></span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with adj_col2:
            st.markdown("##### ✏️ Adjustment Parameters")
            new_stock = st.number_input(
                "New Verified Physical Stock Count (Units)*",
                min_value=0,
                max_value=100000,
                value=curr_stock,
                step=1,
                key="adj_new_stock_input",
                help="Enter physical audit count or initial receiving volume.",
            )

            adj_reason = st.selectbox(
                "Reason for Stock Adjustment*",
                options=[
                    "Physical Audit Discrepancy",
                    "Initial Stock Load (New Product)",
                    "Damaged / Expired Stock Write-off",
                    "Received Unrecorded Delivery",
                    "Customer Return to Stock",
                    "Theft / Shrinkage Correction",
                    "Warehouse Transfer Correction",
                ],
                key="adj_reason_select",
            )

            delta_units = new_stock - curr_stock
            delta_val = delta_units * cost_val
            new_total_val = new_stock * cost_val

            st.markdown(
                f"""
                <div style="background: #1E293B; border-radius: 6px; padding: 12px 14px; margin: 12px 0;">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-size: 0.9rem; color: #94A3B8;">Physical Stock Delta:</span>
                        <strong style="color: {'#10B981' if delta_units > 0 else ('#EF4444' if delta_units < 0 else '#94A3B8')};">
                            {delta_units:+d} units ({'+' if delta_val > 0 else ''}${delta_val:,.2f})
                        </strong>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 6px;">
                        <span style="font-size: 0.9rem; color: #94A3B8;">New Total Inventory Value:</span>
                        <strong style="color: #38BDF8;">${new_total_val:,.2f}</strong>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button("🚀 Apply Stock Adjustment to Database", type="primary", width='stretch', key="btn_apply_stock_adj"):
                if delta_units == 0 and curr_stock > 0:
                    st.info("Stock quantity is unchanged. No adjustments were written.")
                else:
                    with st.spinner("Persisting physical adjustment to SQL Server snapshot..."):
                        ok, msg = adjust_inventory_stock(
                            store_id=adj_store,
                            product_id=adj_prod,
                            new_on_hand_qty=new_stock,
                            reason=adj_reason,
                        )
                        if ok:
                            st.toast(f"✅ {msg}")
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        # 3. Live Store Inventory Position Ledger
        st.markdown("---")
        st.markdown(f"#### 📋 Current Inventory Position Ledger — Store `{adj_store}`")
        st.caption("Real-time on-hand inventory levels and stockout status across all catalog items for the selected store.")

        ledger_records = []
        for _, p in df_all_prods.iterrows():
            pid_str = str(p["product_id"])
            on_hand = stock_lookup.get(pid_str, 0)
            u_cost = float(p["unit_cost_price"])
            inv_val = on_hand * u_cost
            dos = dos_lookup.get(pid_str, 0.0)
            vel = vel_lookup.get(pid_str, 0.0)
            
            if on_hand == 0:
                pos_status = "🔴 STOCKOUT"
            elif dos < 7 and vel > 0:
                pos_status = "🟡 LOW STOCK"
            else:
                pos_status = "🟢 HEALTHY"

            ledger_records.append({
                "SKU ID": pid_str,
                "Product Name": p["product_name"],
                "Category": p["category"],
                "Brand": p["brand"],
                "Stock On-Hand": on_hand,
                "Unit Cost": u_cost,
                "Inventory Value": inv_val,
                "Days of Supply": dos if on_hand > 0 else 0.0,
                "Status": pos_status,
            })

        df_ledger = pd.DataFrame(ledger_records)

        col_l1, col_l2 = st.columns([2, 1])
        with col_l1:
            ledger_search = st.text_input("🔍 Filter Ledger by SKU, Name, or Brand", placeholder="Type to filter...", key="ledger_filter_query")
        with col_l2:
            ledger_stat_filter = st.selectbox("Status Filter", options=["All Positions", "🔴 STOCKOUT", "🟡 LOW STOCK", "🟢 HEALTHY"], key="ledger_status_select")

        view_ledger = df_ledger.copy()
        if ledger_stat_filter != "All Positions":
            view_ledger = view_ledger[view_ledger["Status"] == ledger_stat_filter]
        if ledger_search.strip():
            l_term = ledger_search.strip().lower()
            view_ledger = view_ledger[
                view_ledger["SKU ID"].str.lower().str.contains(l_term)
                | view_ledger["Product Name"].str.lower().str.contains(l_term)
                | view_ledger["Category"].str.lower().str.contains(l_term)
                | view_ledger["Brand"].str.lower().str.contains(l_term)
            ]

        st.caption(f"Showing **{len(view_ledger)}** of **{len(df_ledger)}** inventory records.")
        st.dataframe(
            view_ledger.style.format({
                "Stock On-Hand": "{:,}",
                "Unit Cost": "${:.2f}",
                "Inventory Value": "${:,.2f}",
                "Days of Supply": "{:.1f} days",
            }),
            width='stretch',
            height=300,
            hide_index=True,
        )

# ==============================================================================
# TAB 4: Bulk CSV / Excel File Importer
# ==============================================================================
with tab_files:
    st.markdown("### 📤 Bulk File Ingestion & Migration")
    st.caption("Drag and drop formatted CSV or Excel files to batch import products, suppliers, or inventory counts.")

    f_col1, f_col2 = st.columns([1, 1])

    with f_col1:
        target_entity = st.selectbox(
            "Select Data Type to Import",
            options=["Products", "Suppliers", "Inventory Count Audit"],
            key="file_import_target",
        )

        uploaded_file = st.file_uploader(
            f"Upload {target_entity} File (.csv or .xlsx)",
            type=["csv", "xlsx", "xls"],
            key="file_uploader_widget",
        )

    with f_col2:
        st.markdown("##### 📥 Download Sample CSV Templates")
        st.caption("Use these standardized templates to prepare your upload files:")

        if target_entity == "Products":
            tmpl = "product_id,product_name,category,sub_category,brand,supplier_id,unit_cost_price,unit_retail_price,pack_size\nPRD51,Organic Oat Milk,Beverages,Dairy Alt,Oatly,SUP01,2.50,4.99,6"
            tmpl_name = "products_template.csv"
        elif target_entity == "Suppliers":
            tmpl = "supplier_id,supplier_name,contact_email,mean_lead_time_days,lead_time_std_dev,min_order_qty,service_level_target_pct\nSUP11,National Foods Ltd,orders@national.com,3.5,0.5,24,95.0"
            tmpl_name = "suppliers_template.csv"
        else:
            tmpl = "store_id,product_id,ending_on_hand_qty\nSTR01,PRD01,150"
            tmpl_name = "inventory_count_template.csv"

        st.download_button(
            label=f"⬇️ Download {target_entity} Template (.csv)",
            data=tmpl.encode("utf-8"),
            file_name=tmpl_name,
            mime="text/csv",
            width='stretch',
        )

    if uploaded_file is not None:
        st.markdown("---")
        st.markdown(f"#### 🔍 Pre-Commit Preview & Validation: `{uploaded_file.name}`")

        file_bytes = uploaded_file.getvalue()
        try:
            if uploaded_file.name.endswith(".csv"):
                preview_df = pd.read_csv(io.BytesIO(file_bytes))
            else:
                preview_df = pd.read_excel(io.BytesIO(file_bytes))

            st.dataframe(preview_df.head(10), width='stretch')
            st.caption(f"Showing first {min(10, len(preview_df))} of {len(preview_df)} records.")

            if st.button("⚡ Commit & Ingest into SQL Server", type="primary", width='stretch'):
                with st.spinner("Validating business rules and committing to database..."):
                    ok, msg, stats = validate_and_import_file(
                        file_bytes=file_bytes,
                        filename=uploaded_file.name,
                        target_dataset=target_entity,
                    )
                    if ok:
                        st.toast(f"✅ {msg}")
                        st.success(f"{msg} ({stats.get('imported_rows', 0)} rows committed).")
                        st.balloons()
                    else:
                        st.error(msg)
        except Exception as exc:
            st.error(f"Error reading file preview: {exc}")
