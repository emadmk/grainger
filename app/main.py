#!/usr/bin/env python3
"""
Grainger Product Selection API
A beautiful web interface for browsing and approving/rejecting products.
Port: 9090
"""

from fastapi import FastAPI, Depends, Query, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
import io
import pandas as pd

from database import get_db, init_db, Product, SourceFile

# Initialize FastAPI app
app = FastAPI(
    title="Grainger Product Selection",
    description="Browse and approve/reject products for your business",
    version="2.0.0"
)

# Templates
templates = Jinja2Templates(directory="templates")


# Request models
class BulkStatusRequest(BaseModel):
    product_ids: List[int]
    status: str  # approved or rejected


# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_db()


# ============================================
# API ENDPOINTS
# ============================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the main product selection page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/files")
async def get_source_files(db: Session = Depends(get_db)):
    """Get list of imported source files."""
    files = db.query(SourceFile).order_by(SourceFile.id).all()
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "display_name": f.display_name,
            "product_count": f.product_count,
            "imported_at": f.imported_at
        }
        for f in files
    ]


@app.get("/api/products")
async def get_products(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    segment: Optional[str] = None,
    source_file: Optional[str] = None,
    status: Optional[str] = None,
    manufacturer: Optional[str] = None,
    lead_time: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort_by: str = Query("id", regex="^(id|material_no|price|short_description|mfr_name|status)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$")
):
    """Get paginated list of products with filtering and search."""

    query = db.query(Product)

    # Apply source file filter
    if source_file:
        query = query.filter(Product.source_file == source_file)

    # Apply status filter
    if status:
        query = query.filter(Product.status == status)

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Product.material_no.ilike(search_term),
                Product.short_description.ilike(search_term),
                Product.long_description.ilike(search_term),
                Product.mfr_name.ilike(search_term),
                Product.mfg_number.ilike(search_term)
            )
        )

    # Apply category filter
    if category:
        query = query.filter(Product.category_name == category)

    # Apply segment filter
    if segment:
        query = query.filter(Product.segment_name == segment)

    # Apply manufacturer filter
    if manufacturer:
        query = query.filter(Product.mfr_name == manufacturer)

    # Apply lead time filter
    if lead_time is not None:
        query = query.filter(Product.lead_time == lead_time)

    # Apply price filters
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    # Get total count
    total = query.count()

    # Apply sorting
    sort_column = getattr(Product, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Apply pagination
    offset = (page - 1) * per_page
    products = query.offset(offset).limit(per_page).all()

    # Format response
    return {
        "products": [
            {
                "id": p.id,
                "material_no": p.material_no,
                "short_description": p.short_description,
                "long_description": p.long_description,
                "price": p.price,
                "catalog_price": p.catalog_price,
                "unit_of_issue": p.unit_of_issue,
                "items_per_uoi": p.items_per_uoi,
                "min_order_qty": p.min_order_qty,
                "mfr_name": p.mfr_name,
                "mfg_number": p.mfg_number,
                "mfg_number_non_condensed": p.mfg_number_non_condensed,
                "lead_time": p.lead_time,
                "ship_pack_weight": p.ship_pack_weight,
                "ship_pack_desc": p.ship_pack_desc,
                "ship_pack_height": p.ship_pack_height,
                "ship_pack_length": p.ship_pack_length,
                "ship_pack_width": p.ship_pack_width,
                "sell_pack_desc": p.sell_pack_desc,
                "sell_pack_height": p.sell_pack_height,
                "sell_pack_length": p.sell_pack_length,
                "sell_pack_width": p.sell_pack_width,
                "sell_pack_weight": p.sell_pack_weight,
                "image_url": p.image_url,
                "primary_image": p.primary_image,
                "product_url": p.product_url,
                "msds_ind": p.msds_ind,
                "msds_url_link": p.msds_url_link,
                "hazmat_flag": p.hazmat_flag,
                "taa_compliant": p.taa_compliant,
                "california_prop_65_org": p.california_prop_65_org,
                "california_prop_65_wht": p.california_prop_65_wht,
                "prop65_cancer_chem": p.prop65_cancer_chem,
                "prop65_repro_chem": p.prop65_repro_chem,
                "prop65_warn_scenario": p.prop65_warn_scenario,
                "category_name": p.category_name,
                "family_name": p.family_name,
                "segment_name": p.segment_name,
                "harmonization_code": p.harmonization_code,
                "upc_numbers": p.upc_numbers,
                "unspsc4": p.unspsc4,
                "unspsc_class_id": p.unspsc_class_id,
                "unspsc_class_name": p.unspsc_class_name,
                "unspsc_commodity_id": p.unspsc_commodity_id,
                "unspsc_commodity_name": p.unspsc_commodity_name,
                "unspsc_family_id": p.unspsc_family_id,
                "unspsc_family_name": p.unspsc_family_name,
                "unspsc_segment_id": p.unspsc_segment_id,
                "unspsc_segment_name": p.unspsc_segment_name,
                "country_of_origin": p.country_of_origin,
                "country_of_origin_name": p.country_of_origin_name,
                "jwod": p.jwod,
                "green_material_flag": p.green_material_flag,
                "not4sale_state_list": p.not4sale_state_list,
                "current_catalog_page_no": p.current_catalog_page_no,
                "source_file": p.source_file,
                "status": p.status or 'pending',
                "status_updated_at": p.status_updated_at
            }
            for p in products
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 0
        }
    }


@app.get("/api/categories")
async def get_categories(
    db: Session = Depends(get_db),
    source_file: Optional[str] = None
):
    """Get list of all categories with product counts."""
    query = db.query(
        Product.category_name,
        func.count(Product.id).label('count')
    ).filter(
        Product.category_name != '',
        Product.category_name != None
    )

    if source_file:
        query = query.filter(Product.source_file == source_file)

    categories = query.group_by(Product.category_name).order_by(Product.category_name).all()
    return [{"name": c[0], "count": c[1]} for c in categories if c[0]]


@app.get("/api/segments")
async def get_segments(
    db: Session = Depends(get_db),
    source_file: Optional[str] = None
):
    """Get list of all segments with product counts."""
    query = db.query(
        Product.segment_name,
        func.count(Product.id).label('count')
    ).filter(
        Product.segment_name != '',
        Product.segment_name != None
    )

    if source_file:
        query = query.filter(Product.source_file == source_file)

    segments = query.group_by(Product.segment_name).order_by(Product.segment_name).all()
    return [{"name": s[0], "count": s[1]} for s in segments if s[0]]


@app.get("/api/manufacturers")
async def get_manufacturers(
    db: Session = Depends(get_db),
    source_file: Optional[str] = None
):
    """Get list of all manufacturers with product counts."""
    query = db.query(
        Product.mfr_name,
        func.count(Product.id).label('count')
    ).filter(
        Product.mfr_name != '',
        Product.mfr_name != None
    )

    if source_file:
        query = query.filter(Product.source_file == source_file)

    manufacturers = query.group_by(Product.mfr_name).order_by(Product.mfr_name).all()
    return [{"name": m[0], "count": m[1]} for m in manufacturers if m[0]]


@app.get("/api/lead-times")
async def get_lead_times(
    db: Session = Depends(get_db),
    source_file: Optional[str] = None
):
    """Get list of all lead times with product counts."""
    query = db.query(
        Product.lead_time,
        func.count(Product.id).label('count')
    ).filter(
        Product.lead_time != None
    )

    if source_file:
        query = query.filter(Product.source_file == source_file)

    lead_times = query.group_by(Product.lead_time).order_by(Product.lead_time).all()
    return [{"value": lt[0], "count": lt[1]} for lt in lead_times if lt[0] is not None]


@app.post("/api/products/{product_id}/status/{new_status}")
async def update_product_status(
    product_id: int,
    new_status: str,
    db: Session = Depends(get_db)
):
    """Update a product's status (approved/rejected/pending)."""
    if new_status not in ['pending', 'approved', 'rejected']:
        raise HTTPException(status_code=400, detail="Invalid status")

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.status = new_status
    product.status_updated_at = datetime.now().isoformat()
    db.commit()

    return {"status": "success", "product_id": product_id, "new_status": new_status}


@app.post("/api/products/bulk-status")
async def bulk_update_status(
    request: BulkStatusRequest,
    db: Session = Depends(get_db)
):
    """Bulk update product statuses (for Mark All feature)."""
    if request.status not in ['pending', 'approved', 'rejected']:
        raise HTTPException(status_code=400, detail="Invalid status")

    now = datetime.now().isoformat()
    updated = db.query(Product).filter(Product.id.in_(request.product_ids)).update(
        {"status": request.status, "status_updated_at": now},
        synchronize_session=False
    )
    db.commit()

    return {"status": "success", "updated_count": updated}


@app.get("/api/stats")
async def get_stats(
    db: Session = Depends(get_db),
    source_file: Optional[str] = None
):
    """Get database statistics."""
    query = db.query(Product)

    if source_file:
        query = query.filter(Product.source_file == source_file)

    total_products = query.count()
    pending = query.filter(Product.status == 'pending').count()
    approved = query.filter(Product.status == 'approved').count()
    rejected = query.filter(Product.status == 'rejected').count()

    categories = query.with_entities(func.count(func.distinct(Product.category_name))).scalar()
    segments = query.with_entities(func.count(func.distinct(Product.segment_name))).scalar()

    return {
        "total_products": total_products,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "total_categories": categories or 0,
        "total_segments": segments or 0
    }


@app.get("/api/export/excel")
async def export_excel(
    db: Session = Depends(get_db),
    source_file: Optional[str] = None,
    status: Optional[str] = None
):
    """Export products to Excel file."""
    query = db.query(Product)

    if source_file:
        query = query.filter(Product.source_file == source_file)

    if status:
        query = query.filter(Product.status == status)

    products = query.all()

    if not products:
        raise HTTPException(status_code=400, detail="No products to export")

    # Create DataFrame
    data = []
    for p in products:
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
            "Mfg Number Non-Condensed": p.mfg_number_non_condensed,
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
            "Country of Origin Name": p.country_of_origin_name,
            "JWOD": p.jwod,
            "Green Material Flag": p.green_material_flag,
            "Not For Sale States": p.not4sale_state_list,
            "Catalog Page No": p.current_catalog_page_no,
            "Status": p.status,
            "Source File": p.source_file
        })

    df = pd.DataFrame(data)

    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Products', index=False)
    output.seek(0)

    # Filename
    parts = ["grainger_products"]
    if source_file:
        parts.append(source_file)
    if status:
        parts.append(status)
    parts.append(datetime.now().strftime('%Y%m%d_%H%M%S'))
    filename = "_".join(parts) + ".xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============================================
# RUN SERVER
# ============================================

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("  GRAINGER PRODUCT SELECTION SERVER")
    print("="*60)
    print("  Starting server at http://0.0.0.0:9090")
    print("  Press Ctrl+C to stop")
    print("="*60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=9090)
