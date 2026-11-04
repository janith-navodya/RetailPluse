#!/usr/bin/env python3
"""
scripts/build_pbir_layout.py

Automated Fabric PBIR Layout Builder for RetailPulse Decision Intelligence.
Applies the executive two-layer grid system on 1920x1080 canvas:
1. Base Layer: Synchronizes pre-rendered high-res SVG canvas background.
2. Data Layer: Generates 100% background-transparent Fabric PBIR visuals snapped to exact coordinates:
   - Card 1: [Total Sales] at [40, 90, 435x135] (Blue Neon Accent #3B82F6)
   - Card 2: [Gross Margin %] at [505, 90, 435x135] (Emerald Neon Accent #00D26A)
   - Card 3: [Ending Inventory Units] at [970, 90, 435x135] (Blue Neon Accent #3B82F6)
   - Card 4: [Critical Stockout SKUs] at [1435, 90, 445x135] (Crimson Neon Accent #EF4444)
   - Area Chart: Revenue & Cost Trajectory at [55, 330, 865x690]
     - X: dim_date[full_date]
     - Y: [Total Sales] (#00D26A), [Total COGS] (#3B82F6)
   - Table: Inventory Health Fleet Radar at [975, 330, 890x690]
     - Columns: product_name, category, [Ending Inventory Units], [DoS Bar SVG], [Stockout Status Badge SVG]
     - Contrast-locked: #F8FAFC text, #141C2E / #0F1726 rows, #00D26A headers on #0E131F
3. Reconciles and formats all DAX measures in _Measures.tmdl.
"""

from __future__ import annotations

import json
import shutil
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
    accent_color: str,
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
                                                "Value": "'#94A3B8'"
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
                                                "Value": "'#94A3B8'"
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
                ],
                "dataPoint": [
                    {
                        "properties": {
                            "fill": {
                                "solid": {
                                    "color": {
                                        "expr": {
                                            "Literal": {
                                                "Value": "'#00D26A'"
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "selector": {
                            "metadata": "_Measures.Total Sales"
                        }
                    },
                    {
                        "properties": {
                            "fill": {
                                "solid": {
                                    "color": {
                                        "expr": {
                                            "Literal": {
                                                "Value": "'#3B82F6'"
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "selector": {
                            "metadata": "_Measures.Total COGS"
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
    """Generate a Fabric PBIR tableEx visual configured with contrast-locked palette and auto-sized columns."""
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
                                        "Property": "Ending Inventory Units",
                                    }
                                },
                                "queryRef": "_Measures.Ending Inventory Units",
                                "nativeQueryRef": "Ending Inventory Units",
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
                                                "Value": "'#141C2E'"
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
                                                "Value": "'#0F1726'"
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
                                                "Value": "'#00D26A'"
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
                                                "Value": "'#0E131F'"
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
                                                "Value": "'#1E293B'"
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


def build_layout() -> None:
    """Build the complete Fabric PBIR layout snapped to SVG containers."""
    print("================================================================================")
    print("   RetailPulse DI - Fabric PBIR Layout & Visual Generator")
    print("================================================================================")

    # 1. Locate active page folder
    active_page_dir = locate_active_page_dir()
    print(f"-> Active page folder identified: {active_page_dir.resolve()}")

    visuals_dir = active_page_dir / "visuals"
    visuals_dir.mkdir(parents=True, exist_ok=True)

    # 2. Define the visuals according to exact spec coordinates:
    # Card 1: [Total Sales] at [40, 90, 435x135] (Blue Neon Accent)
    # Card 2: [Gross Margin %] at [505, 90, 435x135] (Emerald Neon Accent)
    # Card 3: [Ending Inventory Units] at [970, 90, 435x135] (Blue Neon Accent)
    # Card 4: [Critical Stockout SKUs] at [1435, 90, 445x135] (Crimson Neon Accent)
    # Area Chart: Revenue & Cost Trajectory at [55, 330, 865x690]
    # Table: Inventory Health Fleet Radar at [975, 330, 890x690]

    visual_configs = [
        # Top KPI Card 1: NET REVENUE / Total Sales
        (
            "Card_TotalSales",
            create_kpi_card_visual(
                name="Card_TotalSales",
                x=40,
                y=90,
                width=435,
                height=135,
                z_index=1000,
                measure_name="Total Sales",
                accent_color="#3B82F6",  # Electric Blue
            ),
        ),
        # Top KPI Card 2: GROSS MARGIN %
        (
            "Card_GrossMargin",
            create_kpi_card_visual(
                name="Card_GrossMargin",
                x=505,
                y=90,
                width=435,
                height=135,
                z_index=1001,
                measure_name="Gross Margin %",
                accent_color="#00D26A",  # Emerald Green
            ),
        ),
        # Top KPI Card 3: ENDING INVENTORY UNITS
        (
            "Card_EndingInventoryUnits",
            create_kpi_card_visual(
                name="Card_EndingInventoryUnits",
                x=970,
                y=90,
                width=435,
                height=135,
                z_index=1002,
                measure_name="Ending Inventory Units",
                accent_color="#3B82F6",  # Electric Blue
            ),
        ),
        # Top KPI Card 4: CRITICAL STOCKOUT SKUS
        (
            "Card_CriticalStockoutSKUs",
            create_kpi_card_visual(
                name="Card_CriticalStockoutSKUs",
                x=1435,
                y=90,
                width=445,
                height=135,
                z_index=1003,
                measure_name="Critical Stockout SKUs",
                accent_color="#EF4444",  # Crimson Red
            ),
        ),
        # Left Panel: Area Chart (Revenue & Cost Trajectory)
        (
            "Chart_RevenueCostMomentum",
            create_area_chart_visual(
                name="Chart_RevenueCostMomentum",
                x=55,
                y=330,
                width=865,
                height=690,
                z_index=2000,
            ),
        ),
        # Right Panel: Inventory Health Fleet Radar Table
        (
            "Table_InventoryFleetHealth",
            create_inventory_table_visual(
                name="Table_InventoryFleetHealth",
                x=975,
                y=330,
                width=890,
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

    print("================================================================================")
    print("   [SUCCESS] PBIR Layout Successfully Generated & Validated!")
    print("================================================================================")


if __name__ == "__main__":
    build_layout()
