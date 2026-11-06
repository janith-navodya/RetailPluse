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

    # Database configuration: Defaults to local Microsoft SQL Server 2025 Developer instance
    # Authentication: Windows Integrated Authentication (-E) | Driver: ODBC Driver 18 for SQL Server
    DB_DIALECT: str = os.getenv("DB_DIALECT", "mssql")
    DB_NAME: str = os.getenv("DB_NAME", "RetailPulseDB")
    MSSQL_DATABASE_URL: str = (
        f"mssql+pyodbc://@localhost/{DB_NAME}?"
        "driver=ODBC+Driver+18+for+SQL+Server&"
        "trusted_connection=yes&"
        "TrustServerCertificate=yes"
    )
    SQLITE_DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'retailpulse.db'}"
    DATABASE_URL: str = os.getenv("DATABASE_URL", MSSQL_DATABASE_URL)
    DB_PATH: Path = BASE_DIR / "data" / "retailpulse.db"

    # Database configuration dict for direct ODBC/pyodbc connections
    DB_CONFIG: dict = {
        "driver": "ODBC Driver 18 for SQL Server",
        "server": "localhost",
        "database": DB_NAME,
        "trusted_connection": "yes",
        "trust_server_certificate": "yes",
    }

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
DB_CONFIG = settings.DB_CONFIG

