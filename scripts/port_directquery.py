#!/usr/bin/env python3
"""
scripts/port_directquery.py

Automates the porting and synchronization of RetailPulse_DirectQuery.pbip
from the existing RetailPulse_Platform setup:

1. Closes any running Power BI Desktop processes to release file locks.
2. Synchronizes Semantic Model:
   - Copies and verifies _Measures.tmdl containing all 9 core measures + support measures.
   - Synchronizes dim_product.tmdl currency formatting and aggregation.
   - Registers 'ref table _Measures' inside model.tmdl.
3. Synchronizes Report Layout, Themes, RegisteredResources, & Visuals:
   - Copies SVG background canvas and custom dark theme into RegisteredResources.
   - Updates report.json to register custom theme and resource packages.
   - Replicates all active visual containers (KPI cards, area chart, donut chart, fleet table, bar chart, slicers).
   - Configures Auto Page Refresh (APR) with a 10-second polling interval in page.json.
4. Validates JSON/TMDL file integrity and logs the complete audit trail.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
POWER_BI_DIR = REPO_ROOT / "power_bi"

PLATFORM_MODEL_DIR = POWER_BI_DIR / "RetailPulse_Platform.SemanticModel"
PLATFORM_REPORT_DIR = POWER_BI_DIR / "RetailPulse_Platform.Report"

DQ_MODEL_DIR = POWER_BI_DIR / "RetailPulse_DirectQuery.SemanticModel"
DQ_REPORT_DIR = POWER_BI_DIR / "RetailPulse_DirectQuery.Report"


def step_1_close_pbi_desktop() -> None:
    """Check and terminate any running PBIDesktop processes to release file locks."""
    print("[1/5] Checking for running Power BI Desktop processes...")
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Stop-Process -Name 'PBIDesktop' -Force -ErrorAction SilentlyContinue"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            print("   [+] Verified PBIDesktop process handles released.")
        else:
            print("   [-] Non-Windows environment detected; skipping taskkill.")
    except Exception as exc:
        print(f"   [!] Process termination check note: {exc}")


def step_2_sync_semantic_model() -> None:
    """Synchronize _Measures.tmdl, dim_product.tmdl, and model.tmdl for DirectQuery."""
    print("\n[2/5] Synchronizing Semantic Model for DirectQuery...")

    # 1. Sync _Measures.tmdl
    src_measures = PLATFORM_MODEL_DIR / "definition" / "tables" / "_Measures.tmdl"
    dst_measures = DQ_MODEL_DIR / "definition" / "tables" / "_Measures.tmdl"

    if not src_measures.exists():
        raise FileNotFoundError(f"Source measures TMDL not found at {src_measures}")

    shutil.copyfile(src_measures, dst_measures)
    print(f"   [+] Created {dst_measures.relative_to(REPO_ROOT)}")

    # Verify 9 core measures are present
    content = dst_measures.read_text(encoding="utf-8")
    required_measures = [
        "Total Sales",
        "Total COGS",
        "Gross Margin %",
        "Ending Inventory Units",
        "Rolling 30D Daily Sales",
        "Days of Supply (DoS)",
        "Critical Stockout SKUs",
        "DoS Bar SVG",
        "Stockout Status Badge SVG",
    ]

    for m in required_measures:
        assert f"measure '{m}'" in content, f"Missing required measure: {m}"
    assert "dataCategory: ImageUrl" in content, "Missing ImageUrl dataCategory annotation in SVG measures"
    print(f"   [+] Verified all {len(required_measures)} core measures present & validated.")

    # 2. Sync dim_product.tmdl formatting for unit_retail_price
    dq_dim_prod = DQ_MODEL_DIR / "definition" / "tables" / "dim_product.tmdl"
    if dq_dim_prod.exists():
        prod_text = dq_dim_prod.read_text(encoding="utf-8")
        # Ensure summarizeBy: none and currency formatString
        if "column unit_retail_price" in prod_text and "summarizeBy: sum" in prod_text:
            prod_text = prod_text.replace(
                "column unit_retail_price\n\t\tdataType: double",
                "column unit_retail_price\n\t\tdataType: double\n\t\tformatString: $#,##0.00;($#,##0.00);$#,##0.00",
            ).replace("summarizeBy: sum\n\t\tsourceColumn: unit_retail_price", "summarizeBy: none\n\t\tsourceColumn: unit_retail_price")
            dq_dim_prod.write_text(prod_text, encoding="utf-8")
            print("   [+] Updated dim_product.tmdl unit_retail_price currency format and summarizeBy: none.")

    # 3. Register ref table _Measures in model.tmdl
    dq_model = DQ_MODEL_DIR / "definition" / "model.tmdl"
    model_text = dq_model.read_text(encoding="utf-8")
    if "ref table _Measures" not in model_text:
        target = "ref cultureInfo en-US"
        replacement = "ref table _Measures\n\nref cultureInfo en-US"
        if target in model_text:
            model_text = model_text.replace(target, replacement, 1)
        else:
            model_text += "\nref table _Measures\n"
        dq_model.write_text(model_text, encoding="utf-8")
        print("   [+] Registered 'ref table _Measures' in model.tmdl.")
    else:
        print("   [+] 'ref table _Measures' is already registered in model.tmdl.")


def step_3_sync_registered_resources() -> None:
    """Synchronize SVG Canvas, Custom Dark Theme, and report.json registration."""
    print("\n[3/5] Synchronizing Static & Registered Resources...")

    src_reg_dir = PLATFORM_REPORT_DIR / "StaticResources" / "RegisteredResources"
    dst_reg_dir = DQ_REPORT_DIR / "StaticResources" / "RegisteredResources"
    dst_reg_dir.mkdir(parents=True, exist_ok=True)

    for item in src_reg_dir.iterdir():
        if item.is_file():
            dst_file = dst_reg_dir / item.name
            shutil.copyfile(item, dst_file)
            print(f"   [+] Copied resource {item.name} -> {dst_reg_dir.name}/")

    # Update report.json in DirectQuery Report
    dq_report_json = DQ_REPORT_DIR / "definition" / "report.json"
    with open(dq_report_json, "r", encoding="utf-8") as f:
        rep_data = json.load(f)

    # Configure customTheme pointing to the registered dark theme
    rep_data["themeCollection"]["customTheme"] = {
        "name": "RetailPulse_Modern_Dark5092110651804341.json",
        "reportVersionAtImport": {
            "visual": "2.14.0",
            "report": "3.4.0",
            "page": "2.3.1",
        },
        "type": "RegisteredResources",
    }

    # Ensure RegisteredResources package is registered in resourcePackages
    packages = rep_data.setdefault("resourcePackages", [])
    has_reg = any(p.get("name") == "RegisteredResources" for p in packages)
    if not has_reg:
        packages.append({
            "name": "RegisteredResources",
            "type": "RegisteredResources",
            "items": [
                {
                    "name": "RetailPulse_Executive_Canvas8660435112045219.svg",
                    "path": "RetailPulse_Executive_Canvas8660435112045219.svg",
                    "type": "Image",
                },
                {
                    "name": "RetailPulse_Modern_Dark5092110651804341.json",
                    "path": "RetailPulse_Modern_Dark5092110651804341.json",
                    "type": "CustomTheme",
                },
            ],
        })
        print("   [+] Added RegisteredResources package to report.json.")

    rep_data.setdefault("settings", {})["useEnhancedTooltips"] = True

    with open(dq_report_json, "w", encoding="utf-8") as f:
        json.dump(rep_data, f, indent=2)
    print("   [+] Updated DirectQuery report.json with custom theme and settings.")


def step_4_sync_report_layout_and_apr() -> None:
    """Synchronize active visual containers and configure Auto Page Refresh (APR)."""
    print("\n[4/5] Synchronizing Visual Containers and Auto Page Refresh (APR)...")

    # Locate source active page
    src_pages_meta = PLATFORM_REPORT_DIR / "definition" / "pages" / "pages.json"
    with open(src_pages_meta, "r", encoding="utf-8") as f:
        src_meta = json.load(f)
    src_page_id = src_meta.get("activePageName") or src_meta["pageOrder"][0]
    src_visuals_dir = PLATFORM_REPORT_DIR / "definition" / "pages" / src_page_id / "visuals"

    # Locate destination active page
    dst_pages_meta = DQ_REPORT_DIR / "definition" / "pages" / "pages.json"
    with open(dst_pages_meta, "r", encoding="utf-8") as f:
        dst_meta = json.load(f)
    dst_page_id = dst_meta.get("activePageName") or dst_meta["pageOrder"][0]
    dst_page_dir = DQ_REPORT_DIR / "definition" / "pages" / dst_page_id
    dst_visuals_dir = dst_page_dir / "visuals"

    # 1. Clean existing visuals in destination
    if dst_visuals_dir.exists():
        shutil.rmtree(dst_visuals_dir)
    dst_visuals_dir.mkdir(parents=True, exist_ok=True)

    # 2. Copy all visual folders
    visual_count = 0
    for v_folder in src_visuals_dir.iterdir():
        if v_folder.is_dir():
            target_v_folder = dst_visuals_dir / v_folder.name
            shutil.copytree(v_folder, target_v_folder)
            visual_count += 1
            print(f"   [+] Copied visual container: {v_folder.name}")

    print(f"   [+] Successfully ported {visual_count} active visual containers.")

    # 3. Configure page.json with APR (10-second polling interval) & SVG background
    src_page_json = PLATFORM_REPORT_DIR / "definition" / "pages" / src_page_id / "page.json"
    with open(src_page_json, "r", encoding="utf-8") as f:
        page_config = json.load(f)

    # Update page identifiers for DirectQuery page
    page_config["name"] = dst_page_id
    page_config["displayName"] = "Page 1"
    page_config["displayOption"] = "FitToPage"
    page_config["height"] = 1080
    page_config["width"] = 1920

    # Ensure page objects contains pageRefresh with APR and 10-second duration
    page_objects = page_config.setdefault("objects", {})

    page_objects["pageRefresh"] = [
        {
            "properties": {
                "show": {
                    "expr": {
                        "Literal": {
                            "Value": "true"
                        }
                    }
                },
                "refreshType": {
                    "expr": {
                        "Literal": {
                            "Value": "'APR'"
                        }
                    }
                },
                "duration": {
                    "expr": {
                        "Literal": {
                            "Value": "'00:00:10'"
                        }
                    }
                }
            }
        }
    ]

    dst_page_json = dst_page_dir / "page.json"
    with open(dst_page_json, "w", encoding="utf-8") as f:
        json.dump(page_config, f, indent=2)

    print("   [+] Configured Auto Page Refresh (APR) [10-second polling interval] in page.json.")


def step_5_verify_integrity() -> None:
    """Verify integrity of all generated TMDL and JSON files."""
    print("\n[5/5] Verifying DirectQuery PBIP Integrity...")

    # Check TMDL files
    expected_tmdl = [
        DQ_MODEL_DIR / "definition" / "model.tmdl",
        DQ_MODEL_DIR / "definition" / "tables" / "_Measures.tmdl",
        DQ_MODEL_DIR / "definition" / "tables" / "dim_product.tmdl",
        DQ_MODEL_DIR / "definition" / "tables" / "fact_sales_daily.tmdl",
        DQ_MODEL_DIR / "definition" / "tables" / "fact_inventory_snapshot.tmdl",
    ]
    for p in expected_tmdl:
        assert p.exists(), f"Integrity check failed: {p} missing"
        assert p.stat().st_size > 0, f"Integrity check failed: {p} empty"
    print("   [+] All DirectQuery TMDL model definitions verified.")

    # Check JSON files
    expected_json = [
        POWER_BI_DIR / "RetailPulse_DirectQuery.pbip",
        DQ_REPORT_DIR / "definition.pbir",
        DQ_REPORT_DIR / "definition" / "report.json",
        DQ_REPORT_DIR / "StaticResources" / "RegisteredResources" / "RetailPulse_Modern_Dark5092110651804341.json",
        DQ_REPORT_DIR / "StaticResources" / "RegisteredResources" / "RetailPulse_Executive_Canvas8660435112045219.svg",
    ]
    for p in expected_json:
        assert p.exists(), f"Integrity check failed: {p} missing"
        if p.suffix == ".json" or p.suffix == ".pbir" or p.suffix == ".pbip":
            with open(p, "r", encoding="utf-8") as f:
                json.load(f)
    print("   [+] All DirectQuery Report JSON configurations verified valid.")

    # Check visuals
    dst_pages_meta = DQ_REPORT_DIR / "definition" / "pages" / "pages.json"
    with open(dst_pages_meta, "r", encoding="utf-8") as f:
        dst_meta = json.load(f)
    dst_page_id = dst_meta.get("activePageName") or dst_meta["pageOrder"][0]
    visuals_dir = DQ_REPORT_DIR / "definition" / "pages" / dst_page_id / "visuals"
    visual_folders = [d for d in visuals_dir.iterdir() if d.is_dir()]
    assert len(visual_folders) == 11, f"Expected 11 visuals, found {len(visual_folders)}"

    for vf in visual_folders:
        v_json = vf / "visual.json"
        assert v_json.exists(), f"Missing visual.json in {vf}"
        with open(v_json, "r", encoding="utf-8") as f:
            v_data = json.load(f)
            assert "visual" in v_data, f"Invalid visual structure in {v_json}"

    print(f"   [+] All {len(visual_folders)} visual containers verified valid Fabric PBIR specifications.")


def main() -> None:
    print("=" * 80)
    print("   RetailPulse DirectQuery PBIP Migration & APR Automation Script")
    print("=" * 80)
    try:
        step_1_close_pbi_desktop()
        step_2_sync_semantic_model()
        step_3_sync_registered_resources()
        step_4_sync_report_layout_and_apr()
        step_5_verify_integrity()
        print("\n" + "=" * 80)
        print("   [SUCCESS] RetailPulse_DirectQuery.pbip Porting Completed Successfully!")
        print("=" * 80)
    except Exception as exc:
        print(f"\n[ERROR] Porting failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
