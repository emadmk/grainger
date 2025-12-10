#!/usr/bin/env python3
"""
Import Grainger product data - Special parser for malformed files.
Handles mixed delimiters (pipe + tab + quotes).
"""

import os
import sys
import re
import pandas as pd
from sqlalchemy.orm import Session
from database import engine, Base, Product, SourceFile, init_db
from datetime import datetime

DATA_DIR = "../data"
BATCH_SIZE = 5000


def clean_value(value):
    """Clean a value - remove tabs, extra spaces, quotes."""
    if value is None:
        return ''
    s = str(value)
    # Remove tabs and replace with space
    s = s.replace('\t', ' ')
    # Remove multiple spaces
    s = re.sub(r'\s+', ' ', s)
    # Remove leading/trailing quotes and spaces
    s = s.strip().strip('"').strip()
    if s.lower() == 'nan':
        return ''
    return s


def clean_price(value):
    """Convert to float."""
    v = clean_value(value)
    if not v:
        return 0.0
    try:
        return float(v.replace(',', '').replace('$', ''))
    except:
        return 0.0


def clean_int(value):
    """Convert to int."""
    v = clean_value(value)
    if not v:
        return 0
    try:
        return int(float(v))
    except:
        return 0


def parse_file1_line(line, header_map):
    """Parse a line from file1 (the problematic format)."""
    # File1 format: values separated by | but some values contain tabs
    # First, split by |
    parts = line.split('|')

    if len(parts) < 10:
        return None

    # Clean all parts
    parts = [clean_value(p) for p in parts]

    # Map to dict based on header positions
    data = {}
    for col_name, idx in header_map.items():
        if idx < len(parts):
            data[col_name] = parts[idx]
        else:
            data[col_name] = ''

    return data


def import_file1(filepath, source_name):
    """Import file1 with special parsing."""
    print(f"\n{'='*60}")
    print(f"📦 Importing: {os.path.basename(filepath)}")
    print(f"   Source: {source_name}")
    print(f"   Method: Custom parser for mixed delimiters")
    print(f"{'='*60}")

    # Define expected columns for file1
    # Based on: Grainger Sku|Short Description|Long Description|Price|Catalog Price|...
    header_map = {
        'sku': 0,
        'short_desc': 1,
        'long_desc': 2,
        'price': 3,
        'catalog_price': 4,
        'unit': 5,
        'items_per_uoi': 6,
        'min_order': 7,
        'mfg_name': 8,
        'mfg_number': 9,
        'mfg_number2': 10,
        'lead_time': 11,
        'image_ref': 12,
        'url': 13,
        'ship_weight': 14,
        'msds_ind': 15,
        'msds_url': 16,
        'hazmat': 17,
        'catalog_page': 18,
        'harmonization': 19,
        'primary_image': 20,
        'country_code': 21,
        'country_name': 22,
        'jwod': 23,
        'green_flag': 24,
        'upc': 25,
        'category': 26,
        'family': 27,
        'segment': 28,
        'unspsc4': 29,
        'unspsc_class_id': 30,
        'unspsc_class_name': 31,
        'unspsc_commodity_id': 32,
        'unspsc_commodity_name': 33,
        'unspsc_family_id': 34,
        'unspsc_family_name': 35,
        'unspsc_segment_id': 36,
        'unspsc_segment_name': 37,
        'not4sale_states': 38,
        'taa_compliant': 39,
        'prop65_org': 40,
        'prop65_wht': 41,
        'prop65_cancer': 42,
        'prop65_repro': 43,
        'prop65_warn': 44,
    }

    total_imported = 0
    total_skipped = 0
    batch = []
    line_num = 0

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        # Skip header
        header = f.readline()
        print(f"  Header: {header[:80]}...")

        for line in f:
            line_num += 1
            line = line.strip()
            if not line:
                continue

            try:
                data = parse_file1_line(line, header_map)
                if not data:
                    total_skipped += 1
                    continue

                sku = clean_value(data.get('sku', ''))
                if not sku:
                    total_skipped += 1
                    continue

                # Build image URL
                image_ref = clean_value(data.get('image_ref', '') or data.get('primary_image', ''))
                if image_ref and not image_ref.startswith('http'):
                    image_url = f"https://static.grainger.com/rp/s/is/image/Grainger/{image_ref}?$s7product$"
                else:
                    image_url = image_ref

                product = {
                    'material_no': sku,
                    'short_description': clean_value(data.get('short_desc', ''))[:500],
                    'long_description': clean_value(data.get('long_desc', '')),
                    'price': clean_price(data.get('price', 0)),
                    'catalog_price': clean_price(data.get('catalog_price', 0)),
                    'unit_of_issue': clean_value(data.get('unit', ''))[:50],
                    'items_per_uoi': clean_int(data.get('items_per_uoi', 1)),
                    'min_order_qty': clean_int(data.get('min_order', 1)),
                    'mfr_name': clean_value(data.get('mfg_name', ''))[:200],
                    'mfg_number': clean_value(data.get('mfg_number', ''))[:100],
                    'mfg_number_non_condensed': clean_value(data.get('mfg_number2', ''))[:100],
                    'lead_time': clean_int(data.get('lead_time', 0)),
                    'ship_pack_weight': clean_price(data.get('ship_weight', 0)),
                    'image_url': image_url[:500] if image_url else '',
                    'primary_image': clean_value(data.get('primary_image', ''))[:200],
                    'product_url': clean_value(data.get('url', ''))[:500],
                    'msds_ind': clean_value(data.get('msds_ind', ''))[:10],
                    'msds_url_link': clean_value(data.get('msds_url', ''))[:500],
                    'hazmat_flag': clean_value(data.get('hazmat', ''))[:10],
                    'taa_compliant': clean_value(data.get('taa_compliant', ''))[:10],
                    'california_prop_65_org': clean_value(data.get('prop65_org', ''))[:10],
                    'california_prop_65_wht': clean_value(data.get('prop65_wht', ''))[:10],
                    'prop65_cancer_chem': clean_value(data.get('prop65_cancer', '')),
                    'prop65_repro_chem': clean_value(data.get('prop65_repro', '')),
                    'prop65_warn_scenario': clean_value(data.get('prop65_warn', '')),
                    'category_name': clean_value(data.get('category', ''))[:200],
                    'family_name': clean_value(data.get('family', ''))[:200],
                    'segment_name': clean_value(data.get('segment', ''))[:200],
                    'harmonization_code': clean_value(data.get('harmonization', ''))[:50],
                    'upc_numbers': clean_value(data.get('upc', ''))[:200],
                    'unspsc4': clean_value(data.get('unspsc4', ''))[:20],
                    'unspsc_class_id': clean_value(data.get('unspsc_class_id', ''))[:20],
                    'unspsc_class_name': clean_value(data.get('unspsc_class_name', ''))[:100],
                    'unspsc_commodity_id': clean_value(data.get('unspsc_commodity_id', ''))[:20],
                    'unspsc_commodity_name': clean_value(data.get('unspsc_commodity_name', ''))[:100],
                    'unspsc_family_id': clean_value(data.get('unspsc_family_id', ''))[:20],
                    'unspsc_family_name': clean_value(data.get('unspsc_family_name', ''))[:100],
                    'unspsc_segment_id': clean_value(data.get('unspsc_segment_id', ''))[:20],
                    'unspsc_segment_name': clean_value(data.get('unspsc_segment_name', ''))[:100],
                    'country_of_origin': clean_value(data.get('country_code', ''))[:20],
                    'country_of_origin_name': clean_value(data.get('country_name', ''))[:100],
                    'jwod': clean_value(data.get('jwod', ''))[:10],
                    'green_material_flag': clean_value(data.get('green_flag', ''))[:10],
                    'not4sale_state_list': clean_value(data.get('not4sale_states', ''))[:200],
                    'current_catalog_page_no': clean_value(data.get('catalog_page', ''))[:20],
                    'source_file': source_name,
                    'status': 'pending'
                }

                batch.append(product)

                if len(batch) >= BATCH_SIZE:
                    with Session(engine) as session:
                        for prod in batch:
                            session.add(Product(**prod))
                        session.commit()
                    total_imported += len(batch)
                    print(f"  ✓ Line {line_num:,}: +{len(batch)} (Total: {total_imported:,})")
                    batch = []

            except Exception as e:
                total_skipped += 1
                if total_skipped < 10:
                    print(f"  ⚠️ Line {line_num} error: {str(e)[:50]}")
                continue

    # Insert remaining
    if batch:
        with Session(engine) as session:
            for prod in batch:
                session.add(Product(**prod))
            session.commit()
        total_imported += len(batch)
        print(f"  ✓ Final batch: +{len(batch)} (Total: {total_imported:,})")

    # Register source
    if total_imported > 0:
        with Session(engine) as session:
            existing = session.query(SourceFile).filter_by(filename=source_name).first()
            if existing:
                existing.product_count = total_imported
            else:
                session.add(SourceFile(
                    filename=source_name,
                    display_name=os.path.basename(filepath).replace('.txt', ''),
                    product_count=total_imported,
                    imported_at=datetime.now().isoformat()
                ))
            session.commit()

    print(f"\n✅ {source_name}: {total_imported:,} imported, {total_skipped:,} skipped")
    return total_imported


def import_file2(filepath, source_name):
    """Import file2 with pandas (clean pipe-delimited)."""
    print(f"\n{'='*60}")
    print(f"📦 Importing: {os.path.basename(filepath)}")
    print(f"   Source: {source_name}")
    print(f"   Method: Pandas (clean pipe-delimited)")
    print(f"{'='*60}")

    total_imported = 0
    total_skipped = 0

    chunks = pd.read_csv(
        filepath,
        sep='|',
        encoding='utf-8',
        encoding_errors='replace',
        chunksize=10000,
        low_memory=False,
        on_bad_lines='skip'
    )

    for chunk_num, df in enumerate(chunks):
        products = []

        if chunk_num == 0:
            print(f"  Columns: {list(df.columns)[:5]}...")

        for _, row in df.iterrows():
            try:
                sku = clean_value(row.get('material_no', ''))
                if not sku:
                    total_skipped += 1
                    continue

                image_ref = clean_value(row.get('Image Ref', '') or row.get('primary_image', ''))
                if image_ref and not image_ref.startswith('http'):
                    image_url = f"https://static.grainger.com/rp/s/is/image/Grainger/{image_ref}?$s7product$"
                else:
                    image_url = image_ref

                product = {
                    'material_no': sku,
                    'short_description': clean_value(row.get('Short Description', ''))[:500],
                    'long_description': clean_value(row.get('Long Description', '')),
                    'price': clean_price(row.get('Price', 0)),
                    'catalog_price': clean_price(row.get('wx_price', 0)),
                    'unit_of_issue': clean_value(row.get('Unit of Issue', ''))[:50],
                    'items_per_uoi': clean_int(row.get('Items Per UOI', 1)),
                    'min_order_qty': clean_int(row.get('Min Order Qty', 1)),
                    'mfr_name': clean_value(row.get('MFR Name', ''))[:200],
                    'mfg_number': clean_value(row.get('Condensed Mfg Number', ''))[:100],
                    'mfg_number_non_condensed': clean_value(row.get('MFG Number non-condensed', ''))[:100],
                    'lead_time': clean_int(row.get('Lead Time', 0)),
                    'ship_pack_weight': clean_price(row.get('Ship Pack Weight', 0)),
                    'ship_pack_desc': clean_value(row.get('Ship Pack Desc', ''))[:50],
                    'ship_pack_height': clean_price(row.get('Ship Pack Height', 0)),
                    'ship_pack_length': clean_price(row.get('Ship Pack Length', 0)),
                    'ship_pack_width': clean_price(row.get('Ship Pack Width', 0)),
                    'sell_pack_desc': clean_value(row.get('Sell Pack Desc', ''))[:50],
                    'sell_pack_height': clean_price(row.get('Sell Pack Height', 0)),
                    'sell_pack_length': clean_price(row.get('Sell Pack Length', 0)),
                    'sell_pack_width': clean_price(row.get('Sell Pack Width', 0)),
                    'sell_pack_weight': clean_price(row.get('Sell Pack Weight', 0)),
                    'image_url': image_url[:500] if image_url else '',
                    'primary_image': clean_value(row.get('primary_image', ''))[:200],
                    'product_url': clean_value(row.get('URL Link', ''))[:500],
                    'msds_ind': clean_value(row.get('MSDS Indicator', ''))[:10],
                    'msds_url_link': clean_value(row.get('MSDS URL Link', ''))[:500],
                    'hazmat_flag': clean_value(row.get('Hazmat Indicator', ''))[:10],
                    'taa_compliant': clean_value(row.get('TAA Compliant', ''))[:10],
                    'california_prop_65_org': clean_value(row.get('california_prop_65_org', ''))[:10],
                    'california_prop_65_wht': clean_value(row.get('california_prop_65_wht', ''))[:10],
                    'prop65_cancer_chem': clean_value(row.get('prop65_cancer_chem', '')),
                    'prop65_repro_chem': clean_value(row.get('prop65_repro_chem', '')),
                    'prop65_warn_scenario': clean_value(row.get('prop65_warn_scenario', '')),
                    'category_name': clean_value(row.get('gds_Categoryname', ''))[:200],
                    'family_name': clean_value(row.get('gds_familyname', ''))[:200],
                    'segment_name': clean_value(row.get('gds_segmentname', ''))[:200],
                    'harmonization_code': clean_value(row.get('Harmonization Code', ''))[:50],
                    'upc_numbers': clean_value(row.get('UPC Numbers', ''))[:200],
                    'unspsc4': clean_value(row.get('UNSPSC4', ''))[:20],
                    'unspsc_class_id': clean_value(row.get('UNSPSC Class ID', ''))[:20],
                    'unspsc_class_name': clean_value(row.get('UNSPSC Class Name', ''))[:100],
                    'unspsc_commodity_id': clean_value(row.get('UNSPSC Commodity ID', ''))[:20],
                    'unspsc_commodity_name': clean_value(row.get('UNSPSC Commodity Name', ''))[:100],
                    'unspsc_family_id': clean_value(row.get('UNSPSC Family ID', ''))[:20],
                    'unspsc_family_name': clean_value(row.get('UNSPSC Family Name', ''))[:100],
                    'unspsc_segment_id': clean_value(row.get('UNSPSC Segment ID', ''))[:20],
                    'unspsc_segment_name': clean_value(row.get('UNSPSC Segment Name', ''))[:100],
                    'country_of_origin': clean_value(row.get('country_of_origin', ''))[:20],
                    'country_of_origin_name': clean_value(row.get('country_of_origin_name', ''))[:100],
                    'jwod': clean_value(row.get('JWOD', ''))[:10],
                    'green_material_flag': clean_value(row.get('Green Material Flag', ''))[:10],
                    'not4sale_state_list': clean_value(row.get('not4sale_state_list', ''))[:200],
                    'current_catalog_page_no': clean_value(row.get('Current Catalog Page No', ''))[:20],
                    'source_file': source_name,
                    'status': 'pending'
                }

                products.append(product)

            except Exception as e:
                total_skipped += 1
                continue

        if products:
            with Session(engine) as session:
                for prod in products:
                    session.add(Product(**prod))
                session.commit()
            total_imported += len(products)

        print(f"  ✓ Chunk {chunk_num + 1}: +{len(products)} (Total: {total_imported:,})")

    # Register source
    if total_imported > 0:
        with Session(engine) as session:
            existing = session.query(SourceFile).filter_by(filename=source_name).first()
            if existing:
                existing.product_count = total_imported
            else:
                session.add(SourceFile(
                    filename=source_name,
                    display_name=os.path.basename(filepath).replace('.txt', ''),
                    product_count=total_imported,
                    imported_at=datetime.now().isoformat()
                ))
            session.commit()

    print(f"\n✅ {source_name}: {total_imported:,} imported, {total_skipped:,} skipped")
    return total_imported


def main():
    print("\n" + "="*60)
    print("  GRAINGER PRODUCT IMPORTER v3.0")
    print("  Dual-format parser")
    print("="*60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    init_db()

    # Find files
    files = []
    for f in sorted(os.listdir(DATA_DIR)):
        if f.endswith(('.txt', '.csv')):
            path = os.path.join(DATA_DIR, f)
            size = os.path.getsize(path) / (1024*1024)
            files.append((path, f, size))
            print(f"  📄 {f} ({size:.1f} MB)")

    if not files:
        print("❌ No files found!")
        return

    total = 0
    for i, (path, name, size) in enumerate(files, 1):
        source = f"file{i}"
        try:
            # File1 (smaller, ~555MB) has malformed format
            # File2 (larger, ~1103MB) has clean format
            if '1219' in name or size < 600:
                count = import_file1(path, source)
            else:
                count = import_file2(path, source)
            total += count
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    print(f"  ✅ COMPLETE! Total: {total:,} products")
    print("="*60)

    with Session(engine) as session:
        for s in session.query(SourceFile).all():
            print(f"  • {s.filename}: {s.display_name} ({s.product_count:,})")

    print(f"\n  Run: python main.py")
    print("="*60)


if __name__ == "__main__":
    main()
