#!/usr/bin/env python3
"""
Optimized export for file2 (large file) - Memory efficient
Usage: python export_file2.py
"""

import os
import sys
import gc
import pandas as pd
from sqlalchemy import create_engine, text
from openpyxl.utils import get_column_letter

# Settings
DB_PATH = "grainger.db"
OUTPUT_DIR = "exports"
SOURCE_FILE = "file2"  # Change this if different
BATCH_SIZE = 50000  # Products per Excel file

def get_column_names():
    return [
        "Material No", "Short Description", "Long Description", "Price", "Catalog Price",
        "Unit of Issue", "Items Per UOI", "Min Order Qty", "Manufacturer", "Mfg Number",
        "Mfg Number (Full)", "Lead Time", "Ship Pack Weight", "Ship Pack Desc",
        "Ship Pack Height", "Ship Pack Length", "Ship Pack Width", "Sell Pack Desc",
        "Sell Pack Height", "Sell Pack Length", "Sell Pack Width", "Sell Pack Weight",
        "Image URL", "Primary Image", "Product URL", "MSDS Indicator", "MSDS URL",
        "Hazmat Flag", "TAA Compliant", "CA Prop 65 Org", "CA Prop 65 Wht",
        "Prop65 Cancer Chem", "Prop65 Repro Chem", "Prop65 Warn Scenario",
        "Category", "Family", "Segment", "Harmonization Code", "UPC Numbers",
        "UNSPSC4", "UNSPSC Class ID", "UNSPSC Class Name", "UNSPSC Commodity ID",
        "UNSPSC Commodity Name", "UNSPSC Family ID", "UNSPSC Family Name",
        "UNSPSC Segment ID", "UNSPSC Segment Name", "Country of Origin",
        "Country Name", "JWOD", "Green Material", "Not For Sale States",
        "Catalog Page", "Status", "Source File"
    ]

def export_file2():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    engine = create_engine(f"sqlite:///{DB_PATH}")

    # Get total count for file2
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM products WHERE source_file = '{SOURCE_FILE}'"))
        total = result.scalar()

    print(f"\n{'='*60}")
    print(f"  EXPORTING FILE2 - Memory Optimized")
    print(f"{'='*60}")
    print(f"  Total products: {total:,}")
    print(f"  Batch size: {BATCH_SIZE:,}")
    print(f"  Expected files: {(total // BATCH_SIZE) + 1}")
    print(f"{'='*60}\n")

    part_num = 1
    offset = 0

    while offset < total:
        print(f"  Processing part {part_num:02d}... ", end="", flush=True)

        # Query batch using raw SQL for efficiency
        query = f"""
            SELECT
                material_no, short_description, long_description, price, catalog_price,
                unit_of_issue, items_per_uoi, min_order_qty, mfr_name, mfg_number,
                mfg_number_non_condensed, lead_time, ship_pack_weight, ship_pack_desc,
                ship_pack_height, ship_pack_length, ship_pack_width, sell_pack_desc,
                sell_pack_height, sell_pack_length, sell_pack_width, sell_pack_weight,
                image_url, primary_image, product_url, msds_ind, msds_url_link,
                hazmat_flag, taa_compliant, california_prop_65_org, california_prop_65_wht,
                prop65_cancer_chem, prop65_repro_chem, prop65_warn_scenario,
                category_name, family_name, segment_name, harmonization_code, upc_numbers,
                unspsc4, unspsc_class_id, unspsc_class_name, unspsc_commodity_id,
                unspsc_commodity_name, unspsc_family_id, unspsc_family_name,
                unspsc_segment_id, unspsc_segment_name, country_of_origin,
                country_of_origin_name, jwod, green_material_flag, not4sale_state_list,
                current_catalog_page_no, status, source_file
            FROM products
            WHERE source_file = '{SOURCE_FILE}'
            LIMIT {BATCH_SIZE} OFFSET {offset}
        """

        # Read directly into DataFrame
        df = pd.read_sql(query, engine)
        df.columns = get_column_names()

        if len(df) == 0:
            break

        # Generate filename
        filename = f"file2_part{part_num:02d}.xlsx"
        filepath = os.path.join(OUTPUT_DIR, filename)

        # Write to Excel without fancy formatting (faster)
        df.to_excel(filepath, index=False, sheet_name='Products', engine='openpyxl')

        print(f"{len(df):,} products -> {filename}")

        # Clean up memory
        del df
        gc.collect()

        offset += BATCH_SIZE
        part_num += 1

    print(f"\n{'='*60}")
    print(f"  EXPORT COMPLETE!")
    print(f"  Files created: {part_num - 1}")
    print(f"  Location: {os.path.abspath(OUTPUT_DIR)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    export_file2()
