#!/usr/bin/env python3
"""
Import Grainger product data from pipe-delimited files into SQLite database.
Handles large files efficiently using chunked processing.
Keeps files separate with source_file tracking.
"""

import os
import sys
import pandas as pd
from sqlalchemy.orm import Session
from database import engine, Base, Product, SourceFile, init_db
from datetime import datetime

# Configuration
CHUNK_SIZE = 10000  # Process 10k rows at a time
DATA_DIR = "../data"


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


def clean_string(value, max_len=None):
    """Clean string value."""
    if pd.isna(value):
        return ''
    s = str(value).strip()
    if s.lower() == 'nan':
        return ''
    if max_len:
        s = s[:max_len]
    return s


def import_file(filepath: str, source_name: str):
    """Import a pipe-delimited file."""
    print(f"\n{'='*60}")
    print(f"📦 Importing: {os.path.basename(filepath)}")
    print(f"{'='*60}")

    total_imported = 0
    total_skipped = 0

    # Try to detect delimiter
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        first_line = f.readline()
        delimiter = '|' if '|' in first_line else '\t'

    print(f"  Detected delimiter: {'pipe (|)' if delimiter == '|' else 'tab'}")

    # Read in chunks
    try:
        chunks = pd.read_csv(
            filepath,
            sep=delimiter,
            encoding='utf-8',
            encoding_errors='replace',
            chunksize=CHUNK_SIZE,
            low_memory=False,
            on_bad_lines='skip'
        )
    except Exception as e:
        print(f"  ❌ Error reading file: {e}")
        return 0

    for chunk_num, df in enumerate(chunks):
        products_to_insert = []

        # Print column names for first chunk
        if chunk_num == 0:
            print(f"  Columns found: {list(df.columns)[:5]}...")

        for _, row in df.iterrows():
            try:
                # Try different column name variations
                material_no = clean_string(
                    row.get('material_no') or
                    row.get('Grainger Sku') or
                    row.get('Material No') or
                    row.get('SKU') or
                    ''
                )

                if not material_no:
                    total_skipped += 1
                    continue

                # Get image URL
                image_ref = clean_string(
                    row.get('Image Ref') or
                    row.get('primary_image') or
                    row.get('image_url') or
                    ''
                )

                # Build full image URL if needed
                if image_ref and not image_ref.startswith('http'):
                    image_url = f"https://static.grainger.com/rp/s/is/image/Grainger/{image_ref}?$s7product$"
                else:
                    image_url = image_ref

                product = {
                    'material_no': material_no,
                    'short_description': clean_string(row.get('Short Description', ''), 500),
                    'long_description': clean_string(row.get('Long Description', '')),
                    'price': clean_price(row.get('Price', 0)),
                    'catalog_price': clean_price(row.get('wx_price') or row.get('Catalog Price', 0)),
                    'unit_of_issue': clean_string(row.get('Unit of Issue', ''), 20),
                    'items_per_uoi': clean_int(row.get('Items Per UOI', 1)),
                    'min_order_qty': clean_int(row.get('Min Order Qty', 1)),
                    'mfr_name': clean_string(row.get('MFR Name') or row.get('Mfg Name', ''), 200),
                    'mfg_number': clean_string(row.get('Condensed Mfg Number') or row.get('Non Condensed Mfg Number', ''), 100),
                    'lead_time': clean_int(row.get('Lead Time', 0)),
                    'image_url': image_url,
                    'product_url': clean_string(row.get('URL Link', ''), 500),
                    'category_name': clean_string(row.get('gds_Categoryname', ''), 200),
                    'family_name': clean_string(row.get('gds_familyname', ''), 200),
                    'segment_name': clean_string(row.get('gds_segmentname', ''), 200),
                    'country_of_origin': clean_string(row.get('country_of_origin_name', ''), 100),
                    'source_file': source_name,
                    'status': 'pending'
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
                        session.add(Product(**prod))
                        total_imported += 1
                    except Exception as e:
                        total_skipped += 1
                try:
                    session.commit()
                except Exception as e:
                    session.rollback()
                    print(f"  ⚠️ Commit error in chunk {chunk_num + 1}: {e}")

        print(f"  ✓ Chunk {chunk_num + 1}: +{len(products_to_insert)} products (Total: {total_imported:,})")

    # Register source file
    with Session(engine) as session:
        existing = session.query(SourceFile).filter_by(filename=source_name).first()
        if existing:
            existing.product_count = total_imported
        else:
            source = SourceFile(
                filename=source_name,
                display_name=os.path.basename(filepath).replace('.txt', '').replace('.csv', ''),
                product_count=total_imported,
                imported_at=datetime.now().isoformat()
            )
            session.add(source)
        session.commit()

    print(f"\n✅ Finished importing {source_name}")
    print(f"   Total imported: {total_imported:,}")
    print(f"   Total skipped: {total_skipped:,}")

    return total_imported


def main():
    print("\n" + "="*60)
    print("  GRAINGER PRODUCT DATA IMPORTER")
    print("  Separate File Mode")
    print("="*60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Initialize database
    print("\n📦 Initializing database...")
    init_db()

    # Find data files
    data_files = []

    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"\n❌ Created empty data folder: {DATA_DIR}")
        print("   Please place your data files there.")
        sys.exit(1)

    for filename in sorted(os.listdir(DATA_DIR)):
        if filename.endswith(('.csv', '.txt', '.dat')):
            filepath = os.path.join(DATA_DIR, filename)
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            data_files.append((filepath, filename, size_mb))
            print(f"  📄 Found: {filename} ({size_mb:.1f} MB)")

    if not data_files:
        print(f"\n❌ No data files found in {DATA_DIR}!")
        print("   Please place your .txt or .csv files in the data folder.")
        sys.exit(1)

    print(f"\n📊 Found {len(data_files)} file(s) to import")

    # Import each file with unique source name
    total_products = 0
    for i, (filepath, filename, size_mb) in enumerate(data_files, 1):
        source_name = f"file{i}"  # file1, file2, etc.
        try:
            count = import_file(filepath, source_name)
            total_products += count
        except Exception as e:
            print(f"\n❌ Error importing {filename}: {e}")

    # Final stats
    print("\n" + "="*60)
    print("  ✅ IMPORT COMPLETE!")
    print("="*60)
    print(f"  Total products in database: {total_products:,}")

    # Show file breakdown
    with Session(engine) as session:
        sources = session.query(SourceFile).all()
        print(f"\n  Files imported:")
        for s in sources:
            print(f"    • {s.filename}: {s.display_name} ({s.product_count:,} products)")

    print(f"\n  Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n  Start server with: python main.py")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
