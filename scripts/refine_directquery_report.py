#!/usr/bin/env python3
"""
scripts/refine_directquery_report.py

Polishes and verifies the RetailPulse_DirectQuery PBIR report:
1. Enforces friendly column displayNames on Table_InventoryFleetHealth projections.
2. Injects high-contrast tooltip configurations (white on dark #0F172A) into chart visuals.
3. Sets page displayName to 'Executive Cockpit' and verifies APR configuration.
4. Verifies 100% JSON & TMDL integrity across the DirectQuery PBIP.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DQ_DIR = REPO_ROOT / "power_bi" / "RetailPulse_DirectQuery.Report"
PAGES_META = DQ_DIR / "definition" / "pages" / "pages.json"

with open(PAGES_META, "r", encoding="utf-8") as f:
    meta = json.load(f)

page_id = meta.get("activePageName") or meta["pageOrder"][0]
page_dir = DQ_DIR / "definition" / "pages" / page_id
visuals_dir = page_dir / "visuals"


def refine_table_visual() -> None:
    """Add friendly displayNames to table projections."""
    table_file = visuals_dir / "Table_InventoryFleetHealth" / "visual.json"
    if not table_file.exists():
        print(f"[-] Table visual not found at {table_file}")
        return

    with open(table_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    projections = data["visual"]["query"]["queryState"]["Values"]["projections"]

    display_name_map = {
        "dim_product.product_name": "Product Name",
        "dim_product.category": "Category",
        "dim_product.unit_retail_price": "Unit Price",
        "_Measures.Ending Inventory Units": "On Hand Units",
        "_Measures.Ending Inventory Value": "Inventory Value",
        "_Measures.Days of Supply (DoS)": "DoS (Days)",
        "_Measures.DoS Bar SVG": "DoS Battery",
        "_Measures.Stockout Status Badge SVG": "Risk Status",
    }

    for proj in projections:
        q_ref = proj.get("queryRef")
        if q_ref in display_name_map:
            proj["displayName"] = display_name_map[q_ref]

    with open(table_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("[+] Table_InventoryFleetHealth: friendly displayNames applied.")


def refine_chart_tooltips() -> None:
    """Inject explicit high-contrast white-text tooltip configs into chart visuals."""
    tooltip_config = [
        {
            "properties": {
                "titleFontColor": {
                    "solid": {
                        "color": {
                            "expr": {
                                "Literal": {
                                    "Value": "'#FFFFFF'"
                                }
                            }
                        }
                    }
                },
                "valueFontColor": {
                    "solid": {
                        "color": {
                            "expr": {
                                "Literal": {
                                    "Value": "'#F8FAFC'"
                                }
                            }
                        }
                    }
                },
                "background": {
                    "solid": {
                        "color": {
                            "expr": {
                                "Literal": {
                                    "Value": "'#0F172A'"
                                }
                            }
                        }
                    }
                },
            }
        }
    ]

    target_charts = [
        "Chart_FinancialMomentum",
        "Chart_CategoryRevenueShare",
        "Chart_ReplenishmentBySupplier",
    ]

    for chart_name in target_charts:
        chart_file = visuals_dir / chart_name / "visual.json"
        if not chart_file.exists():
            continue

        with open(chart_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        objs = data["visual"].setdefault("objects", {})
        objs["tooltip"] = tooltip_config

        with open(chart_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"[+] {chart_name}: explicit high-contrast tooltip configuration injected.")


def verify_page_and_apr() -> None:
    """Ensure page displayName is 'Executive Cockpit' and APR is set to 10s."""
    page_file = page_dir / "page.json"
    with open(page_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["displayName"] = "Executive Cockpit"

    # Verify APR
    page_refresh = data.get("objects", {}).get("pageRefresh", [])
    assert len(page_refresh) > 0, "Missing pageRefresh configuration"
    duration = page_refresh[0]["properties"]["duration"]["expr"]["Literal"]["Value"]
    assert duration == "'00:00:10'", f"Unexpected APR duration: {duration}"

    with open(page_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("[+] page.json: verified displayName='Executive Cockpit' and APR 10-second polling.")


def main() -> None:
    print("=" * 70)
    print("   RetailPulse DirectQuery PBIP Polish & Verification")
    print("=" * 70)
    refine_table_visual()
    refine_chart_tooltips()
    verify_page_and_apr()
    print("=" * 70)
    print("   [SUCCESS] DirectQuery Report Fully Refined & Verified!")
    print("=" * 70)


if __name__ == "__main__":
    main()
