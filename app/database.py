from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./grainger.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    material_no = Column(String(50), index=True)
    short_description = Column(String(500))
    long_description = Column(Text)
    price = Column(Float)
    catalog_price = Column(Float)
    unit_of_issue = Column(String(20))
    items_per_uoi = Column(Integer)
    min_order_qty = Column(Integer)
    mfr_name = Column(String(200))
    mfg_number = Column(String(100))
    lead_time = Column(Integer)
    image_url = Column(String(500))
    product_url = Column(String(500))
    category_name = Column(String(200), index=True)
    family_name = Column(String(200), index=True)
    segment_name = Column(String(200), index=True)
    country_of_origin = Column(String(100))
    source_file = Column(String(100), index=True)  # Which file: file1 or file2

    # Manager decision status: pending, approved, rejected
    status = Column(String(20), default='pending', index=True)
    status_updated_at = Column(String(50))


class SourceFile(Base):
    """Track imported source files"""
    __tablename__ = "source_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(200), unique=True)
    display_name = Column(String(200))
    product_count = Column(Integer, default=0)
    imported_at = Column(String(50))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
