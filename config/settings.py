"""Central configuration for RetailPulse DI Platform."""
import os
from pathlib import Path

# Root project directory
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    # Project paths
    PROJECT_NAME: str = "RetailPulse DI"
    ROOT_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DATA_DIR: Path = BASE_DIR / "data" / "raw"
    PROCESSED_DATA_DIR: Path = BASE_DIR / "data" / "processed"
    QUARANTINE_DATA_DIR: Path = BASE_DIR / "data" / "quarantine"
    SQL_DIR: Path = BASE_DIR / "sql"
    DDL_DIR: Path = BASE_DIR / "sql" / "ddl"
    VIEWS_DIR: Path = BASE_DIR / "sql" / "views"

    # Database configuration (Defaults to SQLite; supports PostgreSQL or SQL Server via env)
    DB_DIALECT: str = os.getenv("DB_DIALECT", "sqlite")
    DB_PATH: Path = BASE_DIR / "data" / "retailpulse.db"
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'retailpulse.db'}")

    # Synthetic data generation parameters
    SIMULATION_DAYS: int = 730  # 2 full calendar years
    START_DATE: str = "2024-01-01"
    NUM_STORES: int = 3
    NUM_PRODUCTS: int = 50
    NUM_SUPPLIERS: int = 10
    RANDOM_SEED: int = 42

    # Data Quality & Quarantine
    INJECT_CORRUPTIONS: bool = True
    CORRUPTION_RATE: float = 0.03  # 3% controlled corruption for testing quarantine

    @classmethod
    def ensure_directories(cls):
        """Ensure all required runtime directories exist."""
        for path in [
            cls.DATA_DIR,
            cls.RAW_DATA_DIR,
            cls.PROCESSED_DATA_DIR,
            cls.QUARANTINE_DATA_DIR,
        ]:
            path.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_directories()
