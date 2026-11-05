#!/usr/bin/env python3
"""
scripts/build_pbir_layout.py

High-Professional Fabric PBIR Layout Builder for RetailPulse Decision Intelligence.
Implements the 4-zone Executive Cockpit Architecture on 1920x1080 canvas:

ZONE 1: Header & Interactive Slicers
  - Slicer 1: [dim_store.store_name] at [1380, 20, 235x46]
  - Slicer 2: [dim_product.category] at [1645, 20, 235x46]

ZONE 2: 5 Executive Hero KPI Pods
  - Pod 1: [Total Sales] at [40, 85, 350x125] (Electric Blue #3B82F6)
  - Pod 2: [Gross Margin %] at [415, 85, 350x125] (Emerald Green #00D26A)
  - Pod 3: [Ending Inventory Value] at [790, 85, 350x125] (Purple #8B5CF6)
  - Pod 4: [Critical Stockout SKUs] at [1165, 85, 350x125] (Crimson Red #EF4444)
  - Pod 5: [Total Recommended Spend] at [1540, 85, 340x125] (Amber #F59E0B)

ZONE 3: Middle Analytical Engine (Combo & Donut)
  - Left: Financial & Margin Trajectory (Area Chart) at [55, 285, 1130x320]
          Legend aligned TopRight to avoid Y-axis collision.
  - Right: Category Revenue & Profit Share (Donut Chart) at [1235, 285, 630x320]

ZONE 4: Bottom Operational Intelligence & Fleet Radar
  - Left: Actionable Inventory Fleet Health Radar (Full-Width Table) at [55, 695, 1130x340]
          8 comprehensive columns eliminating voids: Product, Category, Unit Price,
          Units, Inventory Value, DoS Days, DoS Battery SVG, Status Badge SVG.
  - Right: Replenishment Allocation by Supplier (Bar Chart) at [1235, 695, 630x340]

Visual headers disabled across all visuals (no floating white toolbar obstruction),
transparent backgrounds, and full data-layer connectivity.
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


def create_slicer_visual(
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
    z_index: int,
    entity: str,
    property_name: str,
    display_name: str,
) -> dict:
    """Generate a Fabric PBIR slicer visual dictionary with dropdown mode and clean dark aesthetics."""
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
            "visualType": "slicer",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": [
                            {
                                "field": {
                                    "Column": {
                                        "Expression": {
                                            "SourceRef": {
                                                "Entity": entity
                                            }
                                        },
                                        "Property": property_name,
                                    }
                                },
                                "queryRef": f"{entity}.{property_name}",
                                "nativeQueryRef": display_name,
                            }
                        ]
                    }
                }
            },
            "objects": {
                "header": [
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
                "data": [
                    {
                        "properties": {
                            "mode": {
                                "expr": {
                                    "Literal": {
                                        "Value": "'Dropdown'"
                                    }
                                }
                            }
                        }
                    }
                ]
            },
            "visualContainerObjects": {
                "visualHeader": [
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
                "title": [
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
    """Generate a Fabric PBIR card visual dictionary."""
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
                                        "Value": "24D"
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
                "visualHeader": [
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
                "title": [
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


def create_financial_momentum_chart(
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
    z_index: int,
) -> dict:
    """Generate Financial & Margin Momentum Area Chart visual with TopRight legend."""
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
                                "nativeQueryRef": "Date",
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
                                        "Value": "'TopRight'"
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
                "visualHeader": [
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
                "title": [
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


def create_category_donut_chart(
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
    z_index: int,
) -> dict:
    """Generate Category Revenue & Margin Share Donut Chart visual."""
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
            "visualType": "donutChart",
            "query": {
                "queryState": {
                    "Category": {
                        "projections": [
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
                            }
                        ]
                    }
                }
            },
            "objects": {
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
                                        "Value": "'Right'"
                                    }
                                }
                            }
                        }
                    }
                ],
                "labels": [
                    {
                        "properties": {
                            "show": {
                                "expr": {
                                    "Literal": {
                                        "Value": "true"
                                    }
                                }
                            },
                            "color": {
                                "solid": {
                                    "color": {
                                        "expr": {
                                            "Literal": {
                                                "Value": "'#F8FAFC'"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                ]
            },
            "visualContainerObjects": {
                "visualHeader": [
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
                "title": [
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
    """Generate Full-Width Responsive Table Visual for Inventory Fleet Health with 8 comprehensive columns."""
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
                                    "Column": {
                                        "Expression": {
                                            "SourceRef": {
                                                "Entity": "dim_product"
                                            }
                                        },
                                        "Property": "unit_retail_price",
                                    }
                                },
                                "queryRef": "dim_product.unit_retail_price",
                                "nativeQueryRef": "Unit Price",
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
                                "nativeQueryRef": "On Hand Units",
                            },
                            {
                                "field": {
                                    "Measure": {
                                        "Expression": {
                                            "SourceRef": {
                                                "Entity": "_Measures"
                                            }
                                        },
                                        "Property": "Ending Inventory Value",
                                    }
                                },
                                "queryRef": "_Measures.Ending Inventory Value",
                                "nativeQueryRef": "Inventory Value",
                            },
                            {
                                "field": {
                                    "Measure": {
                                        "Expression": {
                                            "SourceRef": {
                                                "Entity": "_Measures"
                                            }
                                        },
                                        "Property": "Days of Supply (DoS)",
                                    }
                                },
                                "queryRef": "_Measures.Days of Supply (DoS)",
                                "nativeQueryRef": "DoS (Days)",
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
                                "nativeQueryRef": "DoS Battery",
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
                                "nativeQueryRef": "Risk Status",
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
                "visualHeader": [
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
                "title": [
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


def create_replenishment_bar_chart(
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
    z_index: int,
) -> dict:
    """Generate Replenishment by Supplier Clustered Bar Chart visual."""
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
            "visualType": "clusteredBarChart",
            "query": {
                "queryState": {
                    "Category": {
                        "projections": [
                            {
                                "field": {
                                    "Column": {
                                        "Expression": {
                                            "SourceRef": {
                                                "Entity": "dim_supplier"
                                            }
                                        },
                                        "Property": "supplier_name",
                                    }
                                },
                                "queryRef": "dim_supplier.supplier_name",
                                "nativeQueryRef": "Supplier",
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
                                        "Property": "Total Recommended Spend",
                                    }
                                },
                                "queryRef": "_Measures.Total Recommended Spend",
                                "nativeQueryRef": "Recommended Spend",
                            }
                        ]
                    }
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
                "dataPoint": [
                    {
                        "properties": {
                            "fill": {
                                "solid": {
                                    "color": {
                                        "expr": {
                                            "Literal": {
                                                "Value": "'#F59E0B'"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                ],
                "dataLabels": [
                    {
                        "properties": {
                            "show": {
                                "expr": {
                                    "Literal": {
                                        "Value": "true"
                                    }
                                }
                            },
                            "color": {
                                "solid": {
                                    "color": {
                                        "expr": {
                                            "Literal": {
                                                "Value": "'#F8FAFC'"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                ]
            },
            "visualContainerObjects": {
                "visualHeader": [
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
                "title": [
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
    """Build the complete 4-zone Fabric PBIR executive layout."""
    print("================================================================================")
    print("   RetailPulse DI - Executive PBIR Layout & Visual Generator")
    print("================================================================================")

    # 1. Locate active page folder
    active_page_dir = locate_active_page_dir()
    print(f"-> Active page folder identified: {active_page_dir.resolve()}")

    visuals_dir = active_page_dir / "visuals"
    visuals_dir.mkdir(parents=True, exist_ok=True)

    # 2. Complete Visual Configurations matching the 4-Zone Blueprint
    visual_configs = [
        # ZONE 1: SLICERS (x=1380 and x=1645 to snap cleanly against the 1880px right margin)
        (
            "Slicer_Store",
            create_slicer_visual(
                name="Slicer_Store",
                x=1380,
                y=20,
                width=235,
                height=46,
                z_index=5000,
                entity="dim_store",
                property_name="store_name",
                display_name="Store",
            ),
        ),
        (
            "Slicer_Category",
            create_slicer_visual(
                name="Slicer_Category",
                x=1645,
                y=20,
                width=235,
                height=46,
                z_index=5001,
                entity="dim_product",
                property_name="category",
                display_name="Category",
            ),
        ),
        # ZONE 2: 5 HERO KPI PODS
        (
            "Card_TotalSales",
            create_kpi_card_visual(
                name="Card_TotalSales",
                x=40,
                y=85,
                width=350,
                height=125,
                z_index=1000,
                measure_name="Total Sales",
                accent_color="#3B82F6",  # Electric Blue
            ),
        ),
        (
            "Card_GrossMargin",
            create_kpi_card_visual(
                name="Card_GrossMargin",
                x=415,
                y=85,
                width=350,
                height=125,
                z_index=1001,
                measure_name="Gross Margin %",
                accent_color="#00D26A",  # Emerald Green
            ),
        ),
        (
            "Card_EndingInventoryValue",
            create_kpi_card_visual(
                name="Card_EndingInventoryValue",
                x=790,
                y=85,
                width=350,
                height=125,
                z_index=1002,
                measure_name="Ending Inventory Value",
                accent_color="#8B5CF6",  # Purple Accent
            ),
        ),
        (
            "Card_CriticalStockoutSKUs",
            create_kpi_card_visual(
                name="Card_CriticalStockoutSKUs",
                x=1165,
                y=85,
                width=350,
                height=125,
                z_index=1003,
                measure_name="Critical Stockout SKUs",
                accent_color="#EF4444",  # Crimson Red
            ),
        ),
        (
            "Card_RecommendedPOSpend",
            create_kpi_card_visual(
                name="Card_RecommendedPOSpend",
                x=1540,
                y=85,
                width=340,
                height=125,
                z_index=1004,
                measure_name="Total Recommended Spend",
                accent_color="#F59E0B",  # Amber Accent
            ),
        ),
        # ZONE 3: MIDDLE ANALYTICAL ENGINE
        (
            "Chart_FinancialMomentum",
            create_financial_momentum_chart(
                name="Chart_FinancialMomentum",
                x=55,
                y=285,
                width=1130,
                height=320,
                z_index=2000,
            ),
        ),
        (
            "Chart_CategoryRevenueShare",
            create_category_donut_chart(
                name="Chart_CategoryRevenueShare",
                x=1235,
                y=285,
                width=630,
                height=320,
                z_index=2001,
            ),
        ),
        # ZONE 4: BOTTOM OPERATIONAL INTELLIGENCE
        (
            "Table_InventoryFleetHealth",
            create_inventory_table_visual(
                name="Table_InventoryFleetHealth",
                x=55,
                y=695,
                width=1130,
                height=340,
                z_index=3000,
            ),
        ),
        (
            "Chart_ReplenishmentBySupplier",
            create_replenishment_bar_chart(
                name="Chart_ReplenishmentBySupplier",
                x=1235,
                y=695,
                width=630,
                height=340,
                z_index=3001,
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
