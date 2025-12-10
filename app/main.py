#!/usr/bin/env python3
"""
Grainger Product Selection API
A beautiful web interface for browsing and selecting products.
"""

from fastapi import FastAPI, Depends, Query, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional, List
from datetime import datetime
import io
import pandas as pd

from database import get_db, init_db, Product, SelectedProduct

# Initialize FastAPI app
app = FastAPI(
    title="Grainger Product Selection",
    description="Browse and select products for your business",
    version="1.0.0"
)

# Templates
templates = Jinja2Templates(directory="templates")

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


@app.get("/api/products")
async def get_products(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    segment: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort_by: str = Query("material_no", regex="^(material_no|price|short_description|mfr_name)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$")
):
    """Get paginated list of products with filtering and search."""

    query = db.query(Product)

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

    # Get selected product IDs for this page
    material_nos = [p.material_no for p in products]
    selected = db.query(SelectedProduct.material_no).filter(
        SelectedProduct.material_no.in_(material_nos)
    ).all()
    selected_set = {s[0] for s in selected}

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
                "mfr_name": p.mfr_name,
                "mfg_number": p.mfg_number,
                "image_url": p.image_url,
                "product_url": p.product_url,
                "category_name": p.category_name,
                "family_name": p.family_name,
                "segment_name": p.segment_name,
                "lead_time": p.lead_time,
                "is_selected": p.material_no in selected_set
            }
            for p in products
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page
        }
    }


@app.get("/api/categories")
async def get_categories(db: Session = Depends(get_db)):
    """Get list of all categories with product counts."""
    categories = db.query(
        Product.category_name,
        func.count(Product.id).label('count')
    ).filter(
        Product.category_name != '',
        Product.category_name != 'nan'
    ).group_by(Product.category_name).order_by(Product.category_name).all()

    return [{"name": c[0], "count": c[1]} for c in categories if c[0]]


@app.get("/api/segments")
async def get_segments(db: Session = Depends(get_db)):
    """Get list of all segments with product counts."""
    segments = db.query(
        Product.segment_name,
        func.count(Product.id).label('count')
    ).filter(
        Product.segment_name != '',
        Product.segment_name != 'nan'
    ).group_by(Product.segment_name).order_by(Product.segment_name).all()

    return [{"name": s[0], "count": s[1]} for s in segments if s[0]]


@app.post("/api/select/{material_no}")
async def select_product(material_no: str, db: Session = Depends(get_db)):
    """Add a product to the selection list."""
    # Check if product exists
    product = db.query(Product).filter(Product.material_no == material_no).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check if already selected
    existing = db.query(SelectedProduct).filter(SelectedProduct.material_no == material_no).first()
    if existing:
        return {"status": "already_selected", "material_no": material_no}

    # Add to selection
    selected = SelectedProduct(
        material_no=material_no,
        selected_at=datetime.now().isoformat()
    )
    db.add(selected)
    db.commit()

    return {"status": "selected", "material_no": material_no}


@app.delete("/api/select/{material_no}")
async def deselect_product(material_no: str, db: Session = Depends(get_db)):
    """Remove a product from the selection list."""
    selected = db.query(SelectedProduct).filter(SelectedProduct.material_no == material_no).first()
    if selected:
        db.delete(selected)
        db.commit()

    return {"status": "deselected", "material_no": material_no}


@app.get("/api/selected")
async def get_selected_products(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    """Get all selected products with pagination."""
    # Get selected material numbers
    selected_query = db.query(SelectedProduct)
    total = selected_query.count()

    offset = (page - 1) * per_page
    selected_items = selected_query.offset(offset).limit(per_page).all()
    material_nos = [s.material_no for s in selected_items]

    # Get product details
    products = db.query(Product).filter(Product.material_no.in_(material_nos)).all()
    product_map = {p.material_no: p for p in products}

    return {
        "products": [
            {
                "id": product_map[s.material_no].id if s.material_no in product_map else None,
                "material_no": s.material_no,
                "short_description": product_map[s.material_no].short_description if s.material_no in product_map else "",
                "price": product_map[s.material_no].price if s.material_no in product_map else 0,
                "mfr_name": product_map[s.material_no].mfr_name if s.material_no in product_map else "",
                "image_url": product_map[s.material_no].image_url if s.material_no in product_map else "",
                "category_name": product_map[s.material_no].category_name if s.material_no in product_map else "",
                "selected_at": s.selected_at,
                "is_selected": True
            }
            for s in selected_items
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page
        }
    }


@app.get("/api/selected/count")
async def get_selected_count(db: Session = Depends(get_db)):
    """Get count of selected products."""
    count = db.query(SelectedProduct).count()
    return {"count": count}


@app.delete("/api/selected/clear")
async def clear_selected(db: Session = Depends(get_db)):
    """Clear all selected products."""
    db.query(SelectedProduct).delete()
    db.commit()
    return {"status": "cleared"}


@app.get("/api/export/excel")
async def export_excel(db: Session = Depends(get_db)):
    """Export selected products to Excel file."""
    # Get all selected products
    selected = db.query(SelectedProduct).all()
    material_nos = [s.material_no for s in selected]

    if not material_nos:
        raise HTTPException(status_code=400, detail="No products selected")

    # Get product details
    products = db.query(Product).filter(Product.material_no.in_(material_nos)).all()

    # Create DataFrame
    data = []
    for p in products:
        data.append({
            "Material No": p.material_no,
            "Short Description": p.short_description,
            "Long Description": p.long_description,
            "Price": p.price,
            "Catalog Price": p.catalog_price,
            "Unit": p.unit_of_issue,
            "Manufacturer": p.mfr_name,
            "Mfg Number": p.mfg_number,
            "Category": p.category_name,
            "Family": p.family_name,
            "Segment": p.segment_name,
            "Lead Time": p.lead_time,
            "Product URL": p.product_url
        })

    df = pd.DataFrame(data)

    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Selected Products', index=False)
    output.seek(0)

    # Return as download
    filename = f"grainger_selected_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get database statistics."""
    total_products = db.query(Product).count()
    total_selected = db.query(SelectedProduct).count()
    categories = db.query(func.count(func.distinct(Product.category_name))).scalar()
    segments = db.query(func.count(func.distinct(Product.segment_name))).scalar()

    return {
        "total_products": total_products,
        "total_selected": total_selected,
        "total_categories": categories,
        "total_segments": segments
    }


# ============================================
# RUN SERVER
# ============================================

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("  GRAINGER PRODUCT SELECTION SERVER")
    print("="*60)
    print("  Starting server at http://0.0.0.0:8000")
    print("  Press Ctrl+C to stop")
    print("="*60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
