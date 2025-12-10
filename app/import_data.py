#!/usr/bin/env python3
"""
Import Grainger product data from pipe-delimited files into SQLite database.
Handles large files efficiently using chunked processing.
Special handling for malformed files.
"""

import os
import sys
import csv
import pandas as pd
from sqlalchemy.orm import Session
from database import engine, Base, Product, SourceFile, init_db
from datetime import datetime

# Configuration
CHUNK_SIZE = 10000
DATA_DIR = "../data"

# Increase CSV field size limit for large fields
csv.field_size_limit(sys.maxsize)


def clean_price(value):
    """Convert price string to float."""
    if pd.isna(value) or value is None:
        return 0.0
    try:
        return float(str(value).replace(',', '').replace('$', '').strip())
    except:
        return 0.0


def clean_int(value):
    """Convert to integer safely."""
    if pd.isna(value) or value is None:
        return 0
    try:
        return int(float(value))
    except:
        return 0


def clean_string(value, max_len=None):
    """Clean string value."""
    if pd.isna(value) or value is None:
        return ''
    s = str(value).strip()
    if s.lower() == 'nan':
        return ''
    if max_len:
        s = s[:max_len]
    return s


def detect_delimiter(filepath):
    """Detect the delimiter used in the file."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        first_lines = [f.readline() for _ in range(5)]

    # Count delimiters
    pipe_count = sum(line.count('|') for line in first_lines)
    tab_count = sum(line.count('\t') for line in first_lines)

    if pipe_count > tab_count:
        return '|'
    elif tab_count > pipe_count:
        return '\t'
    else:
        return '|'  # default


def import_with_csv_reader(filepath: str, source_name: str, delimiter: str):
    """Import using Python's csv module for problematic files."""
    print(f"  Using CSV reader with delimiter: {repr(delimiter)}")

    total_imported = 0
    total_skipped = 0
    batch = []
    batch_size = 5000

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        # Read header
        header_line = f.readline()
        # Clean header - remove any embedded tabs/special chars
        header = [h.strip().replace('\t', ' ').strip() for h in header_line.split(delimiter)]

        print(f"  Header columns: {header[:5]}...")

        # Create column mapping
        col_map = {}
        for i, h in enumerate(header):
            h_lower = h.lower().replace(' ', '_')
            col_map[h_lower] = i
            col_map[h] = i

        # Find key columns
        sku_col = None
        for name in ['material_no', 'grainger_sku', 'grainger sku', 'sku', 'material no']:
            if name in col_map:
                sku_col = col_map[name]
                break

        if sku_col is None:
            print(f"  ❌ Could not find SKU column!")
            return 0

        # Process rows
        reader = csv.reader(f, delimiter=delimiter, quotechar='"')
        row_count = 0

        for row in reader:
            row_count += 1

            try:
                if len(row) < 5:
                    total_skipped += 1
                    continue

                material_no = clean_string(row[sku_col] if sku_col < len(row) else '')
                if not material_no:
                    total_skipped += 1
                    continue

                def get_val(names, default=''):
                    for name in names:
                        if name in col_map and col_map[name] < len(row):
                            return row[col_map[name]]
                    return default

                # Get image URL
                image_ref = clean_string(get_val(['image_ref', 'primary_image', 'image ref']))
                if image_ref and not image_ref.startswith('http'):
                    image_url = f"https://static.grainger.com/rp/s/is/image/Grainger/{image_ref}?$s7product$"
                else:
                    image_url = image_ref

                product = {
                    'material_no': material_no,
                    'short_description': clean_string(get_val(['short_description', 'short description']), 500),
                    'long_description': clean_string(get_val(['long_description', 'long description'])),
                    'price': clean_price(get_val(['price'])),
                    'catalog_price': clean_price(get_val(['wx_price', 'catalog_price', 'catalog price'])),
                    'unit_of_issue': clean_string(get_val(['unit_of_issue', 'unit of issue']), 20),
                    'items_per_uoi': clean_int(get_val(['items_per_uoi', 'items per uoi'])),
                    'min_order_qty': clean_int(get_val(['min_order_qty', 'min order qty'])),
                    'mfr_name': clean_string(get_val(['mfr_name', 'mfg_name', 'mfr name', 'mfg name']), 200),
                    'mfg_number': clean_string(get_val(['condensed_mfg_number', 'non_condensed_mfg_number', 'condensed mfg number']), 100),
                    'lead_time': clean_int(get_val(['lead_time', 'lead time'])),
                    'image_url': image_url,
                    'product_url': clean_string(get_val(['url_link', 'url link']), 500),
                    'category_name': clean_string(get_val(['gds_categoryname']), 200),
                    'family_name': clean_string(get_val(['gds_familyname']), 200),
                    'segment_name': clean_string(get_val(['gds_segmentname']), 200),
                    'country_of_origin': clean_string(get_val(['country_of_origin_name']), 100),
                    'source_file': source_name,
                    'status': 'pending'
                }

                batch.append(product)

                if len(batch) >= batch_size:
                    with Session(engine) as session:
                        for prod in batch:
                            session.add(Product(**prod))
                        session.commit()
                    total_imported += len(batch)
                    print(f"  ✓ Row {row_count:,}: +{len(batch)} products (Total: {total_imported:,})")
                    batch = []

            except Exception as e:
                total_skipped += 1
                continue

        # Insert remaining
        if batch:
            with Session(engine) as session:
                for prod in batch:
                    session.add(Product(**prod))
                session.commit()
            total_imported += len(batch)

    return total_imported, total_skipped


def import_with_pandas(filepath: str, source_name: str, delimiter: str):
    """Import using pandas for well-formed files."""
    print(f"  Using Pandas with delimiter: {repr(delimiter)}")

    total_imported = 0
    total_skipped = 0

    try:
        chunks = pd.read_csv(
            filepath,
            sep=delimiter,
            encoding='utf-8',
            encoding_errors='replace',
            chunksize=CHUNK_SIZE,
            low_memory=False,
            on_bad_lines='skip',
            quoting=csv.QUOTE_MINIMAL
        )
    except Exception as e:
        print(f"  ❌ Pandas read error: {e}")
        return None, None

    for chunk_num, df in enumerate(chunks):
        products_to_insert = []

        if chunk_num == 0:
            print(f"  Columns found: {list(df.columns)[:5]}...")

        for _, row in df.iterrows():
            try:
                material_no = clean_string(
                    row.get('material_no') or
                    row.get('Grainger Sku') or
                    row.get('Material No') or
                    ''
                )

                if not material_no:
                    total_skipped += 1
                    continue

                image_ref = clean_string(
                    row.get('Image Ref') or
                    row.get('primary_image') or
                    ''
                )

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

        if products_to_insert:
            with Session(engine) as session:
                for prod in products_to_insert:
                    try:
                        session.add(Product(**prod))
                        total_imported += 1
                    except:
                        total_skipped += 1
                session.commit()

        print(f"  ✓ Chunk {chunk_num + 1}: +{len(products_to_insert)} products (Total: {total_imported:,})")

    return total_imported, total_skipped


def import_file(filepath: str, source_name: str):
    """Import a data file with automatic method selection."""
    print(f"\n{'='*60}")
    print(f"📦 Importing: {os.path.basename(filepath)}")
    print(f"   Source name: {source_name}")
    print(f"{'='*60}")

    delimiter = detect_delimiter(filepath)
    print(f"  Detected delimiter: {repr(delimiter)}")

    # Try pandas first
    total_imported, total_skipped = import_with_pandas(filepath, source_name, delimiter)

    # If pandas failed or imported 0, try csv reader
    if total_imported is None or total_imported == 0:
        print(f"\n  ⚠️ Pandas method failed, trying CSV reader...")
        total_imported, total_skipped = import_with_csv_reader(filepath, source_name, delimiter)

    # Register source file
    if total_imported and total_imported > 0:
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

    return total_imported or 0


def main():
    print("\n" + "="*60)
    print("  GRAINGER PRODUCT DATA IMPORTER")
    print("  Version 2.0 - Enhanced Parser")
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
        sys.exit(1)

    for filename in sorted(os.listdir(DATA_DIR)):
        if filename.endswith(('.csv', '.txt', '.dat')):
            filepath = os.path.join(DATA_DIR, filename)
            size_mb = os.path.getsize(filepath) / (1024 * 1024)
            data_files.append((filepath, filename, size_mb))
            print(f"  📄 Found: {filename} ({size_mb:.1f} MB)")

    if not data_files:
        print(f"\n❌ No data files found!")
        sys.exit(1)

    print(f"\n📊 Found {len(data_files)} file(s) to import")

    # Import each file
    total_products = 0
    for i, (filepath, filename, size_mb) in enumerate(data_files, 1):
        source_name = f"file{i}"
        try:
            count = import_file(filepath, source_name)
            total_products += count
        except Exception as e:
            print(f"\n❌ Error importing {filename}: {e}")
            import traceback
            traceback.print_exc()

    # Final stats
    print("\n" + "="*60)
    print("  ✅ IMPORT COMPLETE!")
    print("="*60)
    print(f"  Total products in database: {total_products:,}")

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
