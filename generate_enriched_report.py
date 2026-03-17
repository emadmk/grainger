#!/usr/bin/env python3
"""
Generate enriched Purchase History Excel.
Matches Excel materials against the products DB and creates a combined report.

Usage:
    cd ~/EMad/grainger
    python3 generate_enriched_report.py

Output: Purchase_History_Enriched_YYYYMMDD_HHMMSS.xlsx
"""

import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime
from collections import defaultdict

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILE = os.path.join(SCRIPT_DIR, "Grainger Purchase History - (Mar-26).xlsx")
DB_FILE = os.path.join(SCRIPT_DIR, "app", "grainger.db")
TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
OUTPUT_CSV = os.path.join(SCRIPT_DIR, f"Purchase_History_Enriched_{TIMESTAMP}.csv")
OUTPUT_XLSX = os.path.join(SCRIPT_DIR, f"Purchase_History_Enriched_{TIMESTAMP}.xlsx")


def normalize(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ''
    return str(val).strip().upper()


def score_match(row, db_row, db_columns):
    """Score how well an Excel row matches a DB product."""
    score = 0
    details = []

    def get_db(col):
        idx = db_columns.get(col)
        return db_row[idx] if idx is not None and db_row[idx] else ''

    # Brand Name vs mfr_name
    excel_brand = normalize(row.get('Brand Name', ''))
    db_brand = normalize(get_db('mfr_name'))
    if excel_brand and db_brand:
        if excel_brand == db_brand:
            score += 3; details.append('Brand:EXACT')
        elif excel_brand in db_brand or db_brand in excel_brand:
            score += 1; details.append('Brand:PARTIAL')
        else:
            details.append('Brand:MISMATCH')

    # Material Segment vs segment_name
    excel_seg = normalize(row.get('Material Segment', ''))
    db_seg = normalize(get_db('segment_name'))
    if excel_seg and db_seg:
        if excel_seg == db_seg:
            score += 2; details.append('Segment:EXACT')
        elif excel_seg in db_seg or db_seg in excel_seg:
            score += 1; details.append('Segment:PARTIAL')
        else:
            details.append('Segment:MISMATCH')

    # Material Family vs family_name
    excel_fam = normalize(row.get('Material Family', ''))
    db_fam = normalize(get_db('family_name'))
    if excel_fam and db_fam:
        if excel_fam == db_fam:
            score += 2; details.append('Family:EXACT')
        elif excel_fam in db_fam or db_fam in excel_fam:
            score += 1; details.append('Family:PARTIAL')
        else:
            details.append('Family:MISMATCH')

    # Material Category vs category_name
    excel_cat = normalize(row.get('Material Category', ''))
    db_cat = normalize(get_db('category_name'))
    if excel_cat and db_cat:
        if excel_cat == db_cat:
            score += 2; details.append('Category:EXACT')
        elif excel_cat in db_cat or db_cat in excel_cat:
            score += 1; details.append('Category:PARTIAL')
        else:
            details.append('Category:MISMATCH')

    return score, details


def main():
    print("=" * 60)
    print("  PURCHASE HISTORY ENRICHMENT REPORT")
    print("=" * 60)

    # 1. Check files exist
    if not os.path.exists(EXCEL_FILE):
        print(f"ERROR: Excel file not found: {EXCEL_FILE}")
        sys.exit(1)
    if not os.path.exists(DB_FILE):
        print(f"ERROR: Database not found: {DB_FILE}")
        sys.exit(1)

    # 2. Read Excel
    print(f"\nReading Excel file...")
    ph_df = pd.read_excel(EXCEL_FILE, engine='openpyxl')
    ph_df.columns = [c.strip() for c in ph_df.columns]
    ph_df['Material'] = ph_df['Material'].astype(str).str.strip()
    ph_df = ph_df[ph_df['Material'].notna() & (ph_df['Material'] != '') & (ph_df['Material'] != 'nan')]
    unique_materials = ph_df['Material'].unique().tolist()
    print(f"  Total rows: {len(ph_df):,}")
    print(f"  Unique materials: {len(unique_materials):,}")

    # 3. Query DB
    print(f"\nQuerying database...")
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Get column names
    cur.execute("PRAGMA table_info(products)")
    columns_info = cur.fetchall()
    col_names = [c[1] for c in columns_info]
    col_index = {name: idx for idx, name in enumerate(col_names)}

    # Query in batches
    BATCH = 500
    db_by_material = defaultdict(list)
    total_db_matches = 0

    for i in range(0, len(unique_materials), BATCH):
        batch = unique_materials[i:i + BATCH]
        placeholders = ','.join(['?' for _ in batch])
        cur.execute(f"SELECT * FROM products WHERE material_no IN ({placeholders})", batch)
        rows = cur.fetchall()
        for row in rows:
            mat = row[col_index['material_no']]
            db_by_material[mat].append(row)
            total_db_matches += 1

        if (i // BATCH + 1) % 50 == 0 or i + BATCH >= len(unique_materials):
            print(f"  Queried {min(i + BATCH, len(unique_materials)):,} / {len(unique_materials):,} materials...")

    print(f"  Found {total_db_matches:,} DB records for {len(db_by_material):,} unique materials")
    conn.close()

    # 4. Match and merge
    print(f"\nMatching and merging...")

    # DB columns to include in output
    db_output_cols = {
        'price': 'DB_Price',
        'catalog_price': 'DB_Catalog_Price',
        'short_description': 'DB_Short_Description',
        'long_description': 'DB_Long_Description',
        'unit_of_issue': 'DB_Unit_of_Issue',
        'items_per_uoi': 'DB_Items_Per_UOI',
        'min_order_qty': 'DB_Min_Order_Qty',
        'mfr_name': 'DB_Manufacturer',
        'mfg_number': 'DB_Mfg_Number',
        'mfg_number_non_condensed': 'DB_Mfg_Number_Non_Condensed',
        'lead_time': 'DB_Lead_Time',
        'category_name': 'DB_Category',
        'family_name': 'DB_Family',
        'segment_name': 'DB_Segment',
        'ship_pack_weight': 'DB_Ship_Pack_Weight',
        'ship_pack_desc': 'DB_Ship_Pack_Desc',
        'image_url': 'DB_Image_URL',
        'product_url': 'DB_Product_URL',
        'hazmat_flag': 'DB_Hazmat_Flag',
        'taa_compliant': 'DB_TAA_Compliant',
        'country_of_origin': 'DB_Country_of_Origin',
        'country_of_origin_name': 'DB_Country_Name',
        'harmonization_code': 'DB_Harmonization_Code',
        'upc_numbers': 'DB_UPC_Numbers',
        'green_material_flag': 'DB_Green_Material_Flag',
        'unspsc_class_name': 'DB_UNSPSC_Class_Name',
        'unspsc_commodity_name': 'DB_UNSPSC_Commodity_Name',
        'status': 'DB_Status',
        'source_file': 'DB_Source_File',
    }

    result_rows = []
    matched_count = 0
    not_matched_count = 0
    confidence_counts = defaultdict(int)

    for idx, (_, row) in enumerate(ph_df.iterrows()):
        material = row['Material']
        candidates = db_by_material.get(material, [])

        row_dict = row.to_dict()

        if not candidates:
            row_dict['DB_Match'] = 'NO'
            row_dict['Match_Confidence'] = ''
            row_dict['Match_Details'] = 'No product found in DB'
            not_matched_count += 1
            result_rows.append(row_dict)
            continue

        # Score each candidate
        best_row = None
        best_score = -1
        best_details = []
        for db_row in candidates:
            s, d = score_match(row, db_row, col_index)
            if s > best_score:
                best_score = s
                best_row = db_row
                best_details = d

        # Determine confidence
        has_mismatch = any('MISMATCH' in d for d in best_details)
        if best_score >= 7:
            confidence = 'HIGH'
        elif best_score >= 3 and not has_mismatch:
            confidence = 'MEDIUM'
        elif has_mismatch:
            confidence = 'LOW - CHECK'
        else:
            confidence = 'MATERIAL_ONLY'

        # Add DB columns
        for db_col, output_name in db_output_cols.items():
            ci = col_index.get(db_col)
            row_dict[output_name] = best_row[ci] if ci is not None else ''

        row_dict['DB_Match'] = 'YES'
        row_dict['Match_Confidence'] = confidence
        row_dict['Match_Details'] = '; '.join(best_details) if best_details else 'Material match only'

        matched_count += 1
        confidence_counts[confidence] += 1
        result_rows.append(row_dict)

        if (idx + 1) % 50000 == 0:
            print(f"  Processed {idx + 1:,} / {len(ph_df):,} rows...")

    result_df = pd.DataFrame(result_rows)
    # Free memory
    del result_rows

    # 5. Write CSV first (memory efficient)
    print(f"\nWriting CSV file...")
    result_df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    csv_size = os.path.getsize(OUTPUT_CSV) / (1024 * 1024)
    print(f"  CSV saved: {csv_size:.1f} MB")

    # 6. Convert CSV to Excel in chunks (memory efficient)
    print(f"\nConverting to Excel (chunked writer)...")
    try:
        from openpyxl import Workbook
        wb = Workbook(write_only=True)
        ws = wb.create_sheet('Enriched Data')

        # Write header
        columns = list(result_df.columns)
        ws.append(columns)

        # Write data in chunks to avoid memory issues
        CHUNK = 10000
        total_rows = len(result_df)
        for start in range(0, total_rows, CHUNK):
            end = min(start + CHUNK, total_rows)
            chunk = result_df.iloc[start:end]
            for _, row in chunk.iterrows():
                ws.append([row[c] for c in columns])
            if (start // CHUNK + 1) % 5 == 0:
                print(f"  Written {end:,} / {total_rows:,} rows...")

        # Summary sheet
        ws2 = wb.create_sheet('Summary')
        ws2.append(['Metric', 'Value'])
        summary_rows = [
            ('Total Rows in Purchase History', len(ph_df)),
            ('Unique Materials', len(unique_materials)),
            ('Matched in DB', matched_count),
            ('NOT Matched in DB', not_matched_count),
            ('Match Rate', f"{matched_count / len(ph_df) * 100:.1f}%" if len(ph_df) > 0 else "0%"),
            ('HIGH Confidence', confidence_counts.get('HIGH', 0)),
            ('MEDIUM Confidence', confidence_counts.get('MEDIUM', 0)),
            ('LOW - CHECK (Need Review)', confidence_counts.get('LOW - CHECK', 0)),
            ('MATERIAL_ONLY', confidence_counts.get('MATERIAL_ONLY', 0)),
            ('Generated At', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        ]
        for row in summary_rows:
            ws2.append(list(row))

        wb.save(OUTPUT_XLSX)
        xlsx_size = os.path.getsize(OUTPUT_XLSX) / (1024 * 1024)
        print(f"  Excel saved: {xlsx_size:.1f} MB")
        excel_ok = True
    except Exception as e:
        print(f"  Excel write failed ({e}), CSV is still available")
        excel_ok = False

    print(f"\n{'=' * 60}")
    print(f"  DONE!")
    print(f"  CSV:   {OUTPUT_CSV} ({csv_size:.1f} MB)")
    if excel_ok:
        print(f"  Excel: {OUTPUT_XLSX} ({xlsx_size:.1f} MB)")
    print(f"  Matched: {matched_count:,} / {len(ph_df):,} ({matched_count / len(ph_df) * 100:.1f}%)")
    print(f"  Not matched: {not_matched_count:,}")
    print(f"  HIGH confidence: {confidence_counts.get('HIGH', 0):,}")
    print(f"  MEDIUM confidence: {confidence_counts.get('MEDIUM', 0):,}")
    print(f"  LOW - CHECK: {confidence_counts.get('LOW - CHECK', 0):,}")
    print(f"  MATERIAL_ONLY: {confidence_counts.get('MATERIAL_ONLY', 0):,}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
