from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, Index, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./grainger.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)

    # Basic Info
    material_no = Column(String(50), index=True)
    short_description = Column(String(500))
    long_description = Column(Text)

    # Pricing
    price = Column(Float)
    catalog_price = Column(Float)

    # Ordering
    unit_of_issue = Column(String(50))
    items_per_uoi = Column(Integer)
    min_order_qty = Column(Integer)

    # Manufacturer
    mfr_name = Column(String(200))
    mfg_number = Column(String(100))
    mfg_number_non_condensed = Column(String(100))

    # Shipping & Lead Time
    lead_time = Column(Integer)
    ship_pack_weight = Column(Float)
    ship_pack_desc = Column(String(50))
    ship_pack_height = Column(Float)
    ship_pack_length = Column(Float)
    ship_pack_width = Column(Float)
    sell_pack_desc = Column(String(50))
    sell_pack_height = Column(Float)
    sell_pack_length = Column(Float)
    sell_pack_width = Column(Float)
    sell_pack_weight = Column(Float)

    # Images & URLs
    image_url = Column(String(500))
    primary_image = Column(String(200))
    product_url = Column(String(500))

    # Safety & Compliance
    msds_ind = Column(String(10))
    msds_url_link = Column(String(500))
    hazmat_flag = Column(String(10))
    taa_compliant = Column(String(10))
    california_prop_65_org = Column(String(10))
    california_prop_65_wht = Column(String(10))
    prop65_cancer_chem = Column(Text)
    prop65_repro_chem = Column(Text)
    prop65_warn_scenario = Column(Text)

    # Classification
    category_name = Column(String(200), index=True)
    family_name = Column(String(200), index=True)
    segment_name = Column(String(200), index=True)

    # Codes
    harmonization_code = Column(String(50))
    upc_numbers = Column(String(200))
    unspsc4 = Column(String(20))
    unspsc_class_id = Column(String(20))
    unspsc_class_name = Column(String(100))
    unspsc_commodity_id = Column(String(20))
    unspsc_commodity_name = Column(String(100))
    unspsc_family_id = Column(String(20))
    unspsc_family_name = Column(String(100))
    unspsc_segment_id = Column(String(20))
    unspsc_segment_name = Column(String(100))

    # Country & Flags
    country_of_origin = Column(String(20))
    country_of_origin_name = Column(String(100))
    jwod = Column(String(10))
    green_material_flag = Column(String(10))
    not4sale_state_list = Column(String(200))
    current_catalog_page_no = Column(String(20))

    # Source & Status
    source_file = Column(String(100), index=True)
    status = Column(String(20), default='pending', index=True)
    status_updated_at = Column(String(50))
    status_updated_by = Column(String(100))

    __table_args__ = (
        Index('ix_products_mfr_name', 'mfr_name'),
        Index('ix_products_lead_time', 'lead_time'),
    )


class SourceFile(Base):
    __tablename__ = "source_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(200), unique=True)
    display_name = Column(String(200))
    product_count = Column(Integer, default=0)
    imported_at = Column(String(50))


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True)
    password_hash = Column(String(200))
    display_name = Column(String(200))
    role = Column(String(20), default='user')  # 'admin' or 'user'
    created_at = Column(String(50))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    # Migrate existing database: add new columns and indexes
    try:
        with engine.connect() as conn:
            # Add status_updated_by column if it doesn't exist
            try:
                conn.execute(text("ALTER TABLE products ADD COLUMN status_updated_by VARCHAR(100)"))
                conn.commit()
            except Exception:
                pass  # Column already exists

            # Create indexes
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_products_mfr_name ON products(mfr_name)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_products_lead_time ON products(lead_time)"))
                conn.commit()
            except Exception:
                pass
    except Exception:
        pass
