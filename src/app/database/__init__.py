from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool, QueuePool

import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")

# Optimize SQLite for better concurrency
# Use WAL mode for better read concurrency and performance
connect_args = {"check_same_thread": False}

# For SQLite, use StaticPool for better performance in single-threaded scenarios
# For production databases (PostgreSQL, MySQL), use QueuePool
if DATABASE_URL.startswith("sqlite"):
    # SQLite-specific optimizations
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        poolclass=StaticPool,
        pool_pre_ping=True,  # Verify connections before using
        echo=False,  # Set to True for SQL debugging
    )
    
    # Enable WAL mode for SQLite (better concurrency)
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")  # Faster than FULL, still safe
        cursor.execute("PRAGMA cache_size=10000")  # Increase cache size
        cursor.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp tables
        cursor.execute("PRAGMA busy_timeout=5000")  # Wait up to 5s for locks
        cursor.close()
else:
    # For production databases, use connection pooling
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=10,  # Number of connections to maintain
        max_overflow=20,  # Additional connections beyond pool_size
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,  # Recycle connections after 1 hour
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency for getting database session with proper cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
