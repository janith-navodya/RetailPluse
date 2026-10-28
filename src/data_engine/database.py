"""Database connection handling, migrations, and session management."""
import sqlite3
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import sessionmaker, Session

from config.settings import settings
from config.logging_config import logger


class DatabaseManager:
    """Manages database connectivity, schema migrations, and transaction sessions."""

    def __init__(self, db_url: str = settings.DATABASE_URL):
        self.db_url = db_url
        connect_args = {}
        if "sqlite" in self.db_url:
            connect_args = {"check_same_thread": False}
        self.engine: Engine = create_engine(self.db_url, echo=False, connect_args=connect_args)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def get_session(self) -> Generator[Session, None, None]:
        """Provides a transactional database session."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def run_migrations(self) -> None:
        """Executes ANSI DDL migration scripts idempotently."""
        logger.info("Executing database schema migrations...")
        star_ddl_path = settings.DDL_DIR / "01_star_schema.sql"
        quarantine_ddl_path = settings.DDL_DIR / "02_quarantine_schema.sql"

        for ddl_path in [star_ddl_path, quarantine_ddl_path]:
            if not ddl_path.exists():
                raise FileNotFoundError(f"Migration script not found: {ddl_path}")
            
            with open(ddl_path, "r", encoding="utf-8") as f:
                ddl_sql = f.read()

            if "sqlite" in self.db_url:
                raw_path = str(settings.DB_PATH)
                conn = sqlite3.connect(raw_path)
                conn.execute("PRAGMA foreign_keys = ON;")
                conn.executescript(ddl_sql)
                conn.commit()
                conn.close()
            else:
                with self.engine.begin() as conn:
                    # Split ANSI SQL commands for standard SQLAlchemy execution
                    statements = [s.strip() for s in ddl_sql.split(";") if s.strip()]
                    for statement in statements:
                        conn.execute(text(statement))

            logger.info("Successfully executed migration: %s", ddl_path.name)

    def reset_database(self) -> None:
        """Drops and re-creates all tables (for isolated integration test runs)."""
        logger.warning("Resetting database schema...")
        if "sqlite" in self.db_url:
            if settings.DB_PATH.exists():
                settings.DB_PATH.unlink()
        self.run_migrations()


db_manager = DatabaseManager()

