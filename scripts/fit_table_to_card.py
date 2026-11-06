#!/usr/bin/env python3
"""
scripts/fit_table_to_card.py

Fixes Table_InventoryFleetHealth width and column sizing so it fully fills
the 1160px background container card:
1. Disables autoSizeColumnWidth (set to false).
2. Sets explicit columnWidth for all 8 projections totaling 1110px:
   - Product Name: 220px
   - Category: 130px
   - Unit Price: 100px
   - On Hand Units: 115px
   - Inventory Value: 125px
   - DoS (Days): 100px
   - DoS Battery: 160px (full SVG resolution, no squishing)
   - Risk Status: 160px (full SVG resolution, no squishing)
   Total: 1110px + 15px scrollbar = 1125px inside 1130px visual container.
3. Applies changes to both DirectQuery and Platform report definitions.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REPORTS = [
    REPO_ROOT / "power_bi" / "RetailPulse_DirectQuery.Report",
    REPO_ROOT / "power_bi" / "RetailPulse_Platform.Report",
]

COLUMN_WIDTHS = [
    ("dim_product.product_name", "220D"),
    ("dim_product.category", "130D"),
    ("dim_product.unit_retail_price", "100D"),
    ("_Measures.Ending Inventory Units", "115D"),
    ("_Measures.Ending Inventory Value", "125D"),
    ("_Measures.Days of Supply (DoS)", "100D"),
    ("_Measures.DoS Bar SVG", "160D"),
    ("_Measures.Stockout Status Badge SVG", "160D"),
]


def update_table_visual(report_dir: Path) -> None:
    pages_meta = report_dir / "definition" / "pages" / "pages.json"
    if not pages_meta.exists():
        return
    with open(pages_meta, "r", encoding="utf-8") as f:
        meta = json.load(f)
    page_id = meta.get("activePageName") or meta["pageOrder"][0]
    table_file = report_dir / "definition" / "pages" / page_id / "visuals" / "Table_InventoryFleetHealth" / "visual.json"

    if not table_file.exists():
        print(f"[-] Missing {table_file}")
        return

    with open(table_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Update position: ensure exact snap to card
    data["position"] = {
        "x": 55,
        "y": 700,
        "z": 3000,
        "width": 1130,
        "height": 340,
        "tabOrder": 3000
    }

    objs = data["visual"].setdefault("objects", {})

    # 2. Disable autoSizeColumnWidth so Power BI respects explicit column widths
    for ch in objs.setdefault("columnHeaders", []):
        ch.setdefault("properties", {})["autoSizeColumnWidth"] = {
            "expr": {
                "Literal": {
                    "Value": "false"
                }
            }
        }

    # 3. Inject explicit columnWidth array
    col_width_array = []
    for meta_key, width_val in COLUMN_WIDTHS:
        col_width_array.append({
            "properties": {
                "value": {
                    "expr": {
                        "Literal": {
                            "Value": width_val
                        }
                    }
                }
            },
            "selector": {
                "metadata": meta_key
            }
        })

    objs["columnWidth"] = col_width_array

    with open(table_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    total_w = sum(int(w.rstrip("D")) for _, w in COLUMN_WIDTHS)
    print(f"[+] Updated {report_dir.name} Table_InventoryFleetHealth:")
    print(f"    - autoSizeColumnWidth: false")
    print(f"    - Injected {len(col_width_array)} columnWidth definitions (total: {total_w}px).")
    print(f"    - Visual position: [x=55, y=700, 1130x340].")


def main() -> None:
    print("=" * 75)
    print("   RetailPulse DI - Fit Table to Card Background Automation")
    print("=" * 75)
    for r in REPORTS:
        update_table_visual(r)
    print("=" * 75)
    print("   [SUCCESS] Table successfully configured to fill entire background card!")
    print("=" * 75)


if __name__ == "__main__":
    main()

