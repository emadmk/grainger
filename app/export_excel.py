#!/usr/bin/env python3
"""
Export database to multiple Excel files
Usage: python export_excel.py [--parts 10] [--output /path/to/output]
"""

import os
import sys
import argparse
import math
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from openpyxl.utils import get_column_letter

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import Product, Base

def export_to_excel(db_path="grainger.db", output_dir="exports", parts=10):
    """Export database products to multiple Excel files per source file"""

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Connect to database
    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)
    session = Session()

    # Get unique source files
    source_files = session.query(Product.source_file).distinct().all()
    source_files = [sf[0] for sf in source_files if sf[0]]

    print(f"\n{'='*60}")
    print(f"  GRAINGER DATABASE EXCEL EXPORTER")
    print(f"{'='*60}")
    print(f"  Source files found: {len(source_files)}")
    print(f"  Parts per file: {parts}")
    print(f"  Output directory: {output_dir}")
    print(f"{'='*60}\n")

    all_files = []

    for source_file in source_files:
        print(f"\n[Processing] {source_file}")
        print("-" * 50)

        # Get all products for this source file
        products = session.query(Product).filter(
            Product.source_file == source_file
        ).all()

        total_count = len(products)
        print(f"  Total products: {total_count:,}")

        if total_count == 0:
            print("  Skipping - no products")
            continue

        # Calculate products per part
        per_part = math.ceil(total_count / parts)
        print(f"  Products per file: ~{per_part:,}")

        # Create safe filename from source file
        safe_name = source_file.replace('.txt', '').replace('.csv', '')
        safe_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in safe_name)

        # Export in parts
        for part_num in range(parts):
            start_idx = part_num * per_part
            end_idx = min((part_num + 1) * per_part, total_count)

            if start_idx >= total_count:
                break

            part_products = products[start_idx:end_idx]

            # Convert to DataFrame
            data = []
            for p in part_products:
                data.append({
                    "Material No": p.material_no,
                    "Short Description": p.short_description,
                    "Long Description": p.long_description,
                    "Price": p.price,
                    "Catalog Price": p.catalog_price,
                    "Unit of Issue": p.unit_of_issue,
                    "Items Per UOI": p.items_per_uoi,
                    "Min Order Qty": p.min_order_qty,
                    "Manufacturer": p.mfr_name,
                    "Mfg Number": p.mfg_number,
                    "Mfg Number (Full)": p.mfg_number_non_condensed,
                    "Lead Time": p.lead_time,
                    "Ship Pack Weight": p.ship_pack_weight,
                    "Ship Pack Desc": p.ship_pack_desc,
                    "Ship Pack Height": p.ship_pack_height,
                    "Ship Pack Length": p.ship_pack_length,
                    "Ship Pack Width": p.ship_pack_width,
                    "Sell Pack Desc": p.sell_pack_desc,
                    "Sell Pack Height": p.sell_pack_height,
                    "Sell Pack Length": p.sell_pack_length,
                    "Sell Pack Width": p.sell_pack_width,
                    "Sell Pack Weight": p.sell_pack_weight,
                    "Image URL": p.image_url,
                    "Primary Image": p.primary_image,
                    "Product URL": p.product_url,
                    "MSDS Indicator": p.msds_ind,
                    "MSDS URL": p.msds_url_link,
                    "Hazmat Flag": p.hazmat_flag,
                    "TAA Compliant": p.taa_compliant,
                    "CA Prop 65 Org": p.california_prop_65_org,
                    "CA Prop 65 Wht": p.california_prop_65_wht,
                    "Prop65 Cancer Chem": p.prop65_cancer_chem,
                    "Prop65 Repro Chem": p.prop65_repro_chem,
                    "Prop65 Warn Scenario": p.prop65_warn_scenario,
                    "Category": p.category_name,
                    "Family": p.family_name,
                    "Segment": p.segment_name,
                    "Harmonization Code": p.harmonization_code,
                    "UPC Numbers": p.upc_numbers,
                    "UNSPSC4": p.unspsc4,
                    "UNSPSC Class ID": p.unspsc_class_id,
                    "UNSPSC Class Name": p.unspsc_class_name,
                    "UNSPSC Commodity ID": p.unspsc_commodity_id,
                    "UNSPSC Commodity Name": p.unspsc_commodity_name,
                    "UNSPSC Family ID": p.unspsc_family_id,
                    "UNSPSC Family Name": p.unspsc_family_name,
                    "UNSPSC Segment ID": p.unspsc_segment_id,
                    "UNSPSC Segment Name": p.unspsc_segment_name,
                    "Country of Origin": p.country_of_origin,
                    "Country Name": p.country_of_origin_name,
                    "JWOD": p.jwod,
                    "Green Material": p.green_material_flag,
                    "Not For Sale States": p.not4sale_state_list,
                    "Catalog Page": p.current_catalog_page_no,
                    "Status": p.status,
                    "Source File": p.source_file
                })

            df = pd.DataFrame(data)

            # Generate filename
            filename = f"{safe_name}_part{part_num + 1:02d}.xlsx"
            filepath = os.path.join(output_dir, filename)

            # Write to Excel with formatting
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Products')

                # Auto-adjust column widths
                worksheet = writer.sheets['Products']
                for idx, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).map(len).max() if len(df) > 0 else 0,
                        len(col)
                    )
                    # Limit column width
                    adjusted_width = min(max_length + 2, 50)
                    col_letter = get_column_letter(idx + 1)  # 1-indexed
                    worksheet.column_dimensions[col_letter].width = adjusted_width

            print(f"  Part {part_num + 1:02d}: {len(part_products):,} products -> {filename}")
            all_files.append(filepath)

    session.close()

    print(f"\n{'='*60}")
    print(f"  EXPORT COMPLETE!")
    print(f"{'='*60}")
    print(f"  Total files created: {len(all_files)}")
    print(f"  Output directory: {os.path.abspath(output_dir)}")
    print(f"\n  Download files using:")
    print(f"  scp -r user@server:{os.path.abspath(output_dir)}/* ./")
    print(f"{'='*60}\n")

    return all_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Grainger database to Excel files")
    parser.add_argument("--parts", type=int, default=10, help="Number of parts per source file (default: 10)")
    parser.add_argument("--output", type=str, default="exports", help="Output directory (default: exports)")
    parser.add_argument("--db", type=str, default="grainger.db", help="Database path (default: grainger.db)")

    args = parser.parse_args()

    export_to_excel(
        db_path=args.db,
        output_dir=args.output,
        parts=args.parts
    )
