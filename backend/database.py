"""
database.py - Database connection setup.

Creates:
  - engine:       the connection to PostgreSQL
  - SessionLocal: a factory that gives us a new DB session per request
  - Base:         parent class for all our SQLAlchemy models
  - get_db():     FastAPI dependency that opens a session and always closes it
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Read values from the .env file into environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")

# pool_pre_ping checks the connection is alive before using it
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


def get_db():
    """Give one database session to a request, then close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
