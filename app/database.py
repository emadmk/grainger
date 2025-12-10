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
    material_no = Column(String(50), unique=True, index=True)
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
    source_file = Column(String(50))  # Track which file it came from


class SelectedProduct(Base):
    __tablename__ = "selected_products"

    id = Column(Integer, primary_key=True, index=True)
    material_no = Column(String(50), unique=True, index=True)
    selected_at = Column(String(50))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
