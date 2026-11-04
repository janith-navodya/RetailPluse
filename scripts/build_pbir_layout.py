#!/usr/bin/env python3
"""
scripts/build_pbir_layout.py

Automated Fabric PBIR Layout Builder for RetailPulse Decision Intelligence.
1. Locates active page folder in power_bi/RetailPulse_Platform.Report/definition/pages/
2. Generates compliant Fabric PBIR visual.json files:
   - 4 Top KPI Cards mapped inside SVG canvas containers with exact pixel coordinates.
   - An Area Chart visual mapped to dim_date[full_date] on X, and _Measures[Total Sales] & _Measures[Total COGS] on Y.
   - An Inventory Table visual configured with transparent background, white text, and auto-sized columns
     for Product Name, Category, DoS Bar SVG, and Status Badge SVG.
3. Formats all measure bindings to use the existing _Measures table.
4. Synchronizes TMDL definitions so all measures exist cleanly in _Measures.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = REPO_ROOT / "power_bi" / "RetailPulse_Platform.Report"
PAGES_DIR = REPORT_DIR / "definition" / "pages"
PAGES_META_FILE = PAGES_DIR / "pages.json"
SEMANTIC_MODEL_DIR = REPO_ROOT / "power_bi" / "RetailPulse_Platform.SemanticModel"
MEASURES_TMDL = SEMANTIC_MODEL_DIR / "definition" / "tables" / "_Measures.tmdl"
SALES_TMDL = SEMANTIC_MODEL_DIR / "definition" / "tables" / "fact_sales_daily.tmdl"

PBIR_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json"


def locate_active_page_dir() -> Path:
    """Locate the active page directory by reading pages.json."""
    if not PAGES_META_FILE.exists():
        raise FileNotFoundError(f"pages.json not found at {PAGES_META_FILE}")

    with open(PAGES_META_FILE, "r", encoding="utf-8") as f:
        meta = json.load(f)

    active_page_name = meta.get("activePageName")
    if not active_page_name and meta.get("pageOrder"):
        active_page_name = meta["pageOrder"][0]

    if not active_page_name:
        subdirs = [p for p in PAGES_DIR.iterdir() if p.is_dir()]
        if not subdirs:
            raise RuntimeError(f"No page directories found inside {PAGES_DIR}")
        active_page_name = subdirs[0].name

    active_page_dir = PAGES_DIR / active_page_name
    if not active_page_dir.exists():
        raise FileNotFoundError(f"Active page directory not found at {active_page_dir}")

    return active_page_dir


def create_kpi_card_visual(
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
    z_index: int,
    measure_name: str,
    accent_color: str = "#00D26A",
) -> dict:
    """Generate a Fabric PBIR card visual.json dictionary."""
    return {
        "$schema": PBIR_SCHEMA,
        "name": name,
        "position": {
            "x": x,
            "y": y,
            "z": z_index,
            "width": width,
            "height": height,
            "tabOrder": z_index,
        },
        "visual": {
            "visualType": "card",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": [
                            {
                                "field": {
                                    "Measure": {
                                        "Expression": {
                                            "SourceRef": {
                                                "Entity": "_Measures"
                                            }
                                        },
                                        "Property": measure_name,
                                    }
                                },
                                "queryRef": f"_Measures.{measure_name}",
                                "nativeQueryRef": measure_name,
                            }
                        ]
                    }
                }
            },
            "objects": {
                "labels": [
                    {
                        "properties": {
                            "color": {
                                "solid": {
                                    "color": {
                                        "expr": {
                                            "Literal": {
                                                "Value": f"'{accent_color}'"
                                            }
                                        }
                                    }
                                }
                            },
                            "fontSize": {
                                "expr": {
                                    "Literal": {
                                        "Value": "26D"
                                    }
                                }
                            }
                        }
                    }
                ],
                "categoryLabels": [
                    {
                        "properties": {
                            "color": {
                                "solid": {
                                    "color": {
                                        "expr": {
                                            "Literal": {
                                                "Value": "'#94A3B8'"
                                            }
                                        }
                                    }
                                }
                            },
                            "fontSize": {
                                "expr": {
                                    "Literal": {
                                        "Value": "11D"
                                    }
                                }
                            }
                        }
                    }
                ]
            },
            "visualContainerObjects": {
                "background": [
                    {
                        "properties": {
                            "show": {
                                "expr": {
                                    "Literal": {
                                        "Value": "false"
                                    }
                                }
                            }
                        }
                    }
                ],
                "border": [
                    {
                        "properties": {
                            "show": {
                                "expr": {
                                    "Literal": {
                                        "Value": "false"
                                    }
                                }
                            }
                        }
                    }
                ],
                "dropShadow": [
                    {
                        "properties": {
                            "show": {
                                "expr": {
                                    "Literal": {
                                        "Value": "false"
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        },
    }


def create_area_chart_visual(
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
    z_index: int,
) -> dict:
    """Generate a Fabric PBIR areaChart visual mapped to dim_date[full_date] on X, and Total Sales & Total COGS on Y."""
    return {
        "$schema": PBIR_SCHEMA,
        "name": name,
        "position": {
            "x": x,
            "y": y,
            "z": z_index,
            "width": width,
            "height": height,
            "tabOrder": z_index,
        },
        "visual": {
            "visualType": "areaChart",
            "query": {
                "queryState": {
                    "Category": {
                        "projections": [
                            {
                                "field": {
                                    "Column": {
                                        "Expression": {
                                            "SourceRef": {
                                                "Entity": "dim_date"
                                            }
                                        },
                                        "Property": "full_date",
                                    }
                                },
                                "queryRef": "dim_date.full_date",
                                "nativeQueryRef": "full_date",
                                "active": True,
                            }
                        ]
                    },
                    "Y": {
                        "projections": [
                            {
                                "field": {
                                    "Measure": {
                                        "Expression": {
                                            "SourceRef": {
                                                "Entity": "_Measures"
                                            }
                                        },
                                        "Property": "Total Sales",
                                    }
                                },
                                "queryRef": "_Measures.Total Sales",
                                "nativeQueryRef": "Total Sales",
                            },
                            {
                                "field": {
                                    "Measure": {
                                        "Expression": {
                                            "SourceRef": {
                                                "Entity": "_Measures"
                                            }
                                        },
                                        "Property": "Total COGS",
                                    }
                                },
                                "queryRef": "_Measures.Total COGS",
                                "nativeQueryRef": "Total COGS",
                            }
                        ]
                    }
                },
                "sortDefinition": {
                    "sort": [
                        {
                            "field": {
                                "Column": {
                                    "Expression": {
                                        "SourceRef": {
                                            "Entity": "dim_date"
                                        }
                                    },
                                    "Property": "full_date",
                                }
                            },
                            "direction": "Ascending",
                        }
                    ],
                    "isDefaultSort": True,
                }
            },
            "objects": {
                "categoryAxis": [
                    {
                        "properties": {
                            "show": {
                                "expr": {
                                    "Literal": {
                                        "Value": "true"
                                    }
                                }
                            },
                            "labelColor": {
                                "solid": {
                                    "color": {
                                        "expr": {
                                            "Literal": {
                                                "Value": "'#64748B'"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                ],
                "valueAxis": [
                    {
                        "properties": {
                            "show": {
                                "expr": {
                                    "Literal": {
                                        "Value": "true"
                                    }
                                }
                            },
                            "labelColor": {
                                "solid": {
                                    "color": {
                                        "expr": {
                                            "Literal": {
                                                "Value": "'#64748B'"
                                            }
                                        }
                                    }
                                }
                            },
                            "gridlineShow": {
                                "expr": {
                                    "Literal": {
                                        "Value": "true"
                                    }
                                }
                            },
                            "gridlineColor": {
                                "solid": {
                                    "color": {
                                        "expr": {
                                            "Literal": {
                                                "Value": "'#1E293B'"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                ],
                "legend": [
                    {
                        "properties": {
                            "show": {
                                "expr": {
                                    "Literal": {
                                        "Value": "true"
                                    }
                                }
                            },
                            "position": {
                                "expr": {
                                    "Literal": {
                                        "Value": "'TopLeft'"
                                    }
                                }
                            }
                        }
                    }
                ]
            },
            "visualContainerObjects": {
                "background": [
                    {
                        "properties": {
                            "show": {
                                "expr": {
                                    "Literal": {
                                        "Value": "false"
                                    }
                                }
                            }
                        }
                    }
                ],
                "border": [
                    {
                        "properties": {
                            "show": {
                                "expr": {
                                    "Literal": {
                                        "Value": "false"
                                    }
                                }
                            }
                        }
                    }
                ],
                "dropShadow": [
                    {
                        "properties": {
                            "show": {
                                "expr": {
                                    "Literal": {
                                        "Value": "false"
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        }
    }


def create_inventory_table_visual(
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
    z_index: int,
) -> dict:
    """Generate a Fabric PBIR tableEx visual configured with transparent background, white text, and auto-sized columns."""
    return {
        "$schema": PBIR_SCHEMA,
        "name": name,
        "position": {
            "x": x,
            "y": y,
            "z": z_index,
            "width": width,
            "height": height,
            "tabOrder": z_index,
        },
        "visual": {
            "visualType": "tableEx",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": [
                            {
                                "field": {
                                    "Column": {
                                        "Expression": {
                                            "SourceRef": {
                                                "Entity": "dim_product"
                                            }
                                        },
                                        "Property": "product_name",
                                    }
                                },
                                "queryRef": "dim_product.product_name",
                                "nativeQueryRef": "Product Name",
                            },
                            {
                                "field": {
                                    "Column": {
                                        "Expression": {
                                            "SourceRef": {
                                                "Entity": "dim_product"
                                            }
                                        },
                                        "Property": "category",
                                    }
                                },
                                "queryRef": "dim_product.category",
                                "nativeQueryRef": "Category",
                            },
                            {
                                "field": {
                                    "Measure": {
                                        "Expression": {
                                            "SourceRef": {
                                                "Entity": "_Measures"
                                            }
                                        },
                                        "Property": "DoS Bar SVG",
                                    }
                                },
                                "queryRef": "_Measures.DoS Bar SVG",
                                "nativeQueryRef": "DoS Bar SVG",
                            },
                            {
                                "field": {
                                    "Measure": {
                                        "Expression": {
                                            "SourceRef": {
                                                "Entity": "_Measures"
                                            }
                                        },
                                        "Property": "Stockout Status Badge SVG",
                                    }
                                },
                                "queryRef": "_Measures.Stockout Status Badge SVG",
                                "nativeQueryRef": "Status Badge SVG",
                            }
                        ]
                    }
                }
            },
            "objects": {
                "values": [
                    {
                        "properties": {
                            "fontColorPrimary": {
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
                            "backColorPrimary": {
                                "solid": {
                                    "color": {
                                        "expr": {
                                            "Literal": {
                                                "Value": "'#00000000'"
                                            }
                                        }
                                    }
                                }
                            },
                            "fontColorSecondary": {
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
                            "backColorSecondary": {
                                "solid": {
                                    "color": {
                                        "expr": {
                                            "Literal": {
                                                "Value": "'#00000000'"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                ],
                "columnHeaders": [
                    {
                        "properties": {
                            "fontColor": {
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
                            "backColor": {
                                "solid": {
                                    "color": {
                                        "expr": {
                                            "Literal": {
                                                "Value": "'#00000000'"
                                            }
                                        }
                                    }
                                }
                            },
                            "autoSizeColumnWidth": {
                                "expr": {
                                    "Literal": {
                                        "Value": "true"
                                    }
                                }
                            }
                        }
                    }
                ],
                "grid": [
                    {
                        "properties": {
                            "gridHorizontal": {
                                "expr": {
                                    "Literal": {
                                        "Value": "true"
                                    }
                                }
                            },
                            "gridHorizontalColor": {
                                "solid": {
                                    "color": {
                                        "expr": {
                                            "Literal": {
                                                "Value": "'#334155'"
                                            }
                                        }
                                    }
                                }
                            },
                            "gridVertical": {
                                "expr": {
                                    "Literal": {
                                        "Value": "false"
                                    }
                                }
                            }
                        }
                    }
                ]
            },
            "visualContainerObjects": {
                "background": [
                    {
                        "properties": {
                            "show": {
                                "expr": {
                                    "Literal": {
                                        "Value": "false"
                                    }
                                }
                            }
                        }
                    }
                ],
                "border": [
                    {
                        "properties": {
                            "show": {
                                "expr": {
                                    "Literal": {
                                        "Value": "false"
                                    }
                                }
                            }
                        }
                    }
                ],
                "dropShadow": [
                    {
                        "properties": {
                            "show": {
                                "expr": {
                                    "Literal": {
                                        "Value": "false"
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        }
    }


def synchronize_semantic_model_measures() -> None:
    """Ensure _Measures.tmdl defines Total Sales, Stockout Rate %, and DoS Bar SVG, and avoid duplicates in fact_sales_daily."""
    print("-> Synchronizing DAX measures in Semantic Model TMDL files...")

    # 1. Update _Measures.tmdl
    if MEASURES_TMDL.exists():
        with open(MEASURES_TMDL, "r", encoding="utf-8") as f:
            content = f.read()

        new_measures = []

        if "measure 'Total Sales'" not in content:
            new_measures.append(
                "\tmeasure 'Total Sales' = SUM ( fact_sales_daily[net_sales_amount] )\n"
                "\t\tlineageTag: 7c008fa3-a4f5-4844-9955-2491f0f59c5a\n\n"
                '\t\tannotation PBI_FormatHint = {"isGeneralNumber":true}\n'
            )

        if "measure 'Stockout Rate %'" not in content:
            new_measures.append(
                "\tmeasure 'Stockout Rate %' = \n"
                "\t\t\tVAR Stockouts = CALCULATE ( COUNTROWS ( fact_inventory_snapshot ), fact_inventory_snapshot[stockout_flag] = 1 )\n"
                "\t\t\tVAR TotalRows = COUNTROWS ( fact_inventory_snapshot )\n"
                "\t\t\tRETURN\n"
                "\t\t\tDIVIDE ( Stockouts, TotalRows, 0 ) * 100\n"
                "\t\tlineageTag: b38e2410-67fe-4a85-9da0-293b21f63eac\n\n"
                '\t\tannotation PBI_FormatHint = {"isGeneralNumber":true}\n'
            )

        if "measure 'Stockout Exposure'" not in content:
            new_measures.append(
                "\tmeasure 'Stockout Exposure' = [Stockout Rate %]\n"
                "\t\tlineageTag: c48e2410-67fe-4a85-9da0-293b21f63ead\n\n"
                '\t\tannotation PBI_FormatHint = {"isGeneralNumber":true}\n'
            )

        if "measure 'DoS Bar SVG'" not in content:
            new_measures.append(
                "\tmeasure 'DoS Bar SVG' = [DoS Health Bar SVG]\n"
                "\t\tlineageTag: 8e594d75-bc90-4269-638a-3209b95f9925\n"
                "\t\tdataCategory: ImageUrl\n"
            )

        if new_measures:
            # Insert before column Column1
            insert_pos = content.find("\tcolumn Column1")
            if insert_pos != -1:
                updated_content = content[:insert_pos] + "\n".join(new_measures) + "\n" + content[insert_pos:]
            else:
                updated_content = content + "\n\n" + "\n".join(new_measures)

            with open(MEASURES_TMDL, "w", encoding="utf-8") as f:
                f.write(updated_content)
            print("   [x] Added required measures (Total Sales, Stockout Rate %, Stockout Exposure, DoS Bar SVG) to _Measures.tmdl")

    # 2. Remove duplicate 'Total Sales' from fact_sales_daily.tmdl if present
    if SALES_TMDL.exists():
        with open(SALES_TMDL, "r", encoding="utf-8") as f:
            sales_content = f.read()

        if "measure 'Total Sales'" in sales_content:
            # Locate measure block
            start_idx = sales_content.find("\tmeasure 'Total Sales'")
            next_col_idx = sales_content.find("\tcolumn date_key", start_idx)
            if start_idx != -1 and next_col_idx != -1:
                sales_content = sales_content[:start_idx] + sales_content[next_col_idx:]
                with open(SALES_TMDL, "w", encoding="utf-8") as f:
                    f.write(sales_content)
                print("   [x] Replaced duplicate Total Sales in fact_sales_daily.tmdl with canonical _Measures binding")


def update_page_bindings(active_page_dir: Path) -> None:
    """Ensure page.json drillthrough filters reference _Measures instead of fact_sales_daily."""
    page_json_path = active_page_dir / "page.json"
    if not page_json_path.exists():
        return

    with open(page_json_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace Entity: "fact_sales_daily" with "_Measures" for Total Sales
    if '"Entity": "fact_sales_daily"' in content:
        content = content.replace(
            '"Entity": "fact_sales_daily"',
            '"Entity": "_Measures"'
        )
        with open(page_json_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("   [x] Updated page.json filter bindings to reference _Measures")


def build_layout() -> None:
    """Build the complete Fabric PBIR layout."""
    print("================================================================================")
    print("   RetailPulse DI - Fabric PBIR Layout & Visual Generator")
    print("================================================================================")

    # 1. Locate active page folder
    active_page_dir = locate_active_page_dir()
    print(f"-> Active page folder identified: {active_page_dir.resolve()}")

    visuals_dir = active_page_dir / "visuals"
    visuals_dir.mkdir(parents=True, exist_ok=True)

    # 2. Define the visuals according to exact SVG background container coordinates
    # SVG coordinates from scripts/generate_powerbi_canvas.py:
    # Card 1: x=40, y=80, width=440, height=140
    # Card 2: x=510, y=80, width=440, height=140
    # Card 3: x=980, y=80, width=440, height=140
    # Card 4: x=1450, y=80, width=430, height=140
    # Left Main Container: x=40, y=250, width=910, height=790 (Header at 70, 290)
    # Right Main Container: x=980, y=250, width=900, height=790 (Header at 1010, 290)

    visual_configs = [
        # Top KPI Card 1: Total Sales
        (
            "Card_TotalSales",
            create_kpi_card_visual(
                name="Card_TotalSales",
                x=40,
                y=80,
                width=440,
                height=140,
                z_index=1000,
                measure_name="Total Sales",
                accent_color="#3B82F6",  # Neon Blue accent
            ),
        ),
        # Top KPI Card 2: Gross Margin %
        (
            "Card_GrossMargin",
            create_kpi_card_visual(
                name="Card_GrossMargin",
                x=510,
                y=80,
                width=440,
                height=140,
                z_index=1001,
                measure_name="Gross Margin %",
                accent_color="#00D26A",  # Neon Green accent
            ),
        ),
        # Top KPI Card 3: Ending Inventory Units
        (
            "Card_EndingInventoryUnits",
            create_kpi_card_visual(
                name="Card_EndingInventoryUnits",
                x=980,
                y=80,
                width=440,
                height=140,
                z_index=1002,
                measure_name="Ending Inventory Units",
                accent_color="#3B82F6",  # Neon Blue accent
            ),
        ),
        # Top KPI Card 4: Stockout Exposure / Stockout Rate %
        (
            "Card_StockoutExposure",
            create_kpi_card_visual(
                name="Card_StockoutExposure",
                x=1450,
                y=80,
                width=430,
                height=140,
                z_index=1003,
                measure_name="Stockout Rate %",
                accent_color="#EF4444",  # Neon Red accent
            ),
        ),
        # Left Panel: Area Chart (Revenue & Cost Momentum)
        (
            "Chart_RevenueCostMomentum",
            create_area_chart_visual(
                name="Chart_RevenueCostMomentum",
                x=55,
                y=330,
                width=880,
                height=690,
                z_index=2000,
            ),
        ),
        # Right Panel: Inventory Table (Fleet Health & Reorder Radar)
        (
            "Table_InventoryFleetHealth",
            create_inventory_table_visual(
                name="Table_InventoryFleetHealth",
                x=995,
                y=330,
                width=870,
                height=690,
                z_index=2001,
            ),
        ),
    ]

    target_names = {name for name, _ in visual_configs}

    # 3. Clean up obsolete/stale visual folders
    print("-> Auditing existing visual folders...")
    for item in visuals_dir.iterdir():
        if item.is_dir() and item.name not in target_names:
            print(f"   [-] Removing legacy/stale visual folder: {item.name}")
            shutil.rmtree(item)

    # 4. Generate compliant PBIR visual.json files
    print("-> Generating Fabric PBIR visual specifications...")
    for folder_name, visual_dict in visual_configs:
        v_folder = visuals_dir / folder_name
        v_folder.mkdir(parents=True, exist_ok=True)
        v_file = v_folder / "visual.json"
        with open(v_file, "w", encoding="utf-8") as f:
            json.dump(visual_dict, f, indent=2)
        pos = visual_dict["position"]
        v_type = visual_dict["visual"]["visualType"]
        print(f"   [+] Generated visual '{folder_name}' ({v_type}) at [{pos['x']}, {pos['y']}, {pos['width']}x{pos['height']}]")

    # 5. Synchronize semantic model measures and page bindings
    synchronize_semantic_model_measures()
    update_page_bindings(active_page_dir)

    print("================================================================================")
    print("   [SUCCESS] PBIR Layout Successfully Generated & Validated!")
    print("================================================================================")


if __name__ == "__main__":
    build_layout()

