import leipzigerflow.models
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from leipzigerflow.config.database_config import load_database_config

DATABASE_CONFIG = load_database_config()
DATABASE_URL = DATABASE_CONFIG.url

_engine_options = {"echo": False, "future": True, "pool_pre_ping": True}
if DATABASE_CONFIG.mode == "sqlite":
    _engine_options["connect_args"] = {"check_same_thread": False, "timeout": 30}

engine = create_engine(DATABASE_URL, **_engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
