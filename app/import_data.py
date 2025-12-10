#!/usr/bin/env python3
"""
Import Grainger product data from CSV/pipe-delimited files into SQLite database.
Handles large files efficiently using chunked processing.
"""

import os
import sys
import pandas as pd
from sqlalchemy.orm import Session
from database import engine, Base, Product, init_db
from datetime import datetime

# Configuration
CHUNK_SIZE = 10000  # Process 10k rows at a time
DATA_DIR = "./data"


def clean_price(value):
    """Convert price string to float."""
    if pd.isna(value):
        return 0.0
    try:
        return float(str(value).replace(',', '').replace('$', '').strip())
    except:
        return 0.0


def clean_int(value):
    """Convert to integer safely."""
    if pd.isna(value):
        return 0
    try:
        return int(float(value))
    except:
        return 0


def import_main_file(filepath: str, source_name: str):
    """Import the main 1.5GB pipe-delimited file."""
    print(f"\n{'='*60}")
    print(f"Importing: {filepath}")
    print(f"{'='*60}")

    total_imported = 0
    total_skipped = 0

    # Read in chunks
    chunks = pd.read_csv(
        filepath,
        sep='|',
        encoding='utf-8',
        encoding_errors='replace',
        chunksize=CHUNK_SIZE,
        low_memory=False,
        on_bad_lines='skip'
    )

    for chunk_num, df in enumerate(chunks):
        products_to_insert = []

        for _, row in df.iterrows():
            try:
                # Map columns - adjust based on actual column names
                material_no = str(row.get('material_no', row.get('Grainger Sku', ''))).strip()

                if not material_no or material_no == 'nan':
                    total_skipped += 1
                    continue

                product = {
                    'material_no': material_no,
                    'short_description': str(row.get('Short Description', ''))[:500],
                    'long_description': str(row.get('Long Description', '')),
                    'price': clean_price(row.get('Price', 0)),
                    'catalog_price': clean_price(row.get('wx_price', row.get('Catalog Price', 0))),
                    'unit_of_issue': str(row.get('Unit of Issue', ''))[:20],
                    'items_per_uoi': clean_int(row.get('Items Per UOI', 1)),
                    'min_order_qty': clean_int(row.get('Min Order Qty', 1)),
                    'mfr_name': str(row.get('MFR Name', row.get('Mfg Name', '')))[:200],
                    'mfg_number': str(row.get('Condensed Mfg Number', row.get('Non Condensed Mfg Number', '')))[:100],
                    'lead_time': clean_int(row.get('Lead Time', 0)),
                    'image_url': str(row.get('Image Ref', row.get('primary_image', '')))[:500],
                    'product_url': str(row.get('URL Link', ''))[:500],
                    'category_name': str(row.get('gds_Categoryname', ''))[:200],
                    'family_name': str(row.get('gds_familyname', ''))[:200],
                    'segment_name': str(row.get('gds_segmentname', ''))[:200],
                    'country_of_origin': str(row.get('country_of_origin_name', ''))[:100],
                    'source_file': source_name
                }

                products_to_insert.append(product)

            except Exception as e:
                total_skipped += 1
                continue

        # Bulk insert
        if products_to_insert:
            with Session(engine) as session:
                for prod in products_to_insert:
                    try:
                        existing = session.query(Product).filter_by(material_no=prod['material_no']).first()
                        if not existing:
                            session.add(Product(**prod))
                            total_imported += 1
                        else:
                            total_skipped += 1
                    except:
                        total_skipped += 1
                session.commit()

        print(f"  Chunk {chunk_num + 1}: Imported {len(products_to_insert)} products (Total: {total_imported})")

    print(f"\n✅ Finished importing {source_name}")
    print(f"   Total imported: {total_imported:,}")
    print(f"   Total skipped: {total_skipped:,}")

    return total_imported


def main():
    print("\n" + "="*60)
    print("  GRAINGER PRODUCT DATA IMPORTER")
    print("="*60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Initialize database
    print("\n📦 Initializing database...")
    init_db()

    # Find data files
    data_files = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(('.csv', '.txt', '.dat')):
            filepath = os.path.join(DATA_DIR, filename)
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            data_files.append((filepath, filename, size_mb))
            print(f"  Found: {filename} ({size_mb:.1f} MB)")

    if not data_files:
        print("\n❌ No data files found in ./data/ directory!")
        print("   Please place your CSV files in the data folder.")
        sys.exit(1)

    # Import each file
    total_products = 0
    for filepath, filename, size_mb in data_files:
        try:
            count = import_main_file(filepath, filename)
            total_products += count
        except Exception as e:
            print(f"\n❌ Error importing {filename}: {e}")

    # Final stats
    print("\n" + "="*60)
    print("  IMPORT COMPLETE!")
    print("="*60)
    print(f"  Total products in database: {total_products:,}")
    print(f"  Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n  You can now start the server with: python main.py")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
