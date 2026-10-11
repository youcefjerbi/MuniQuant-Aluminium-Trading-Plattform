import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/muniquant.db")

def make_engine(url):
    # SQLite allows one writer; wait up to 30 s for a concurrent write instead of failing after 5 s.
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def foreign_keys(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
    return engine
