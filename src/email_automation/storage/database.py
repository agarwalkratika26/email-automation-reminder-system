"""
Database Connection & Session Management.

Initializes SQLite via SQLAlchemy with thread-safe session factories
and provides the DeclarativeBase for model definitions.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from src.email_automation.config import settings

# For SQLite, check_same_thread=False allows FastAPI threads to safely use connections.
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False  # Set to True for verbose SQL logging in development
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ScopedSession = scoped_session(SessionLocal)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency yielding a database session per request,
    ensuring deterministic connection cleanup and rollback on exception.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Creates all database tables defined in the models module.
    Safe to call repeatedly (idempotent).
    """
    # Import models here to register metadata with Base before create_all
    import src.email_automation.storage.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
