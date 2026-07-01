import os
import logging
from pathlib import Path
from datetime import datetime
import psycopg2
from dotenv import load_dotenv
import pandas as pd

# defining paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# load environment variables
load_dotenv(PROJECT_ROOT / ".env")

# logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

# connect to database
def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# read raw excel file
def read_raw_file():
    raw_file = PROJECT_ROOT / "data" / "raw" / "sales_data_raw.xlsx"

    if not raw_file.exists():
        logger.error(f"Raw file not found: {raw_file}")
        raise FileNotFoundError(f"Raw file not found: {raw_file}")

    df = pd.read_excel(raw_file, header=7)
    df.columns = [str(col).strip() for col in df.columns]

    logger.info("Raw file loaded")
    logger.info(f"Shape: {df.shape}")
    logger.info(f"Columns: {df.columns.tolist()}")

    return df

# validate the loaded data
def validate_schema(df):
    expected_columns = [
        "Date",
        "Miti",
        "Inv.No",
        "Customer",
        "Product Group",
        "Product",
        "Uom",
        "Qty",
        "Rate",
        "B. Amount",
        "DISCOUNT",
        "VAT",
        "ROUND OFF",
        "Total Amount",
    ]

    actual_columns = df.columns.tolist()

    if len(actual_columns) != len(expected_columns):
        logger.error(
            f"Column count mismatch. Expected {len(expected_columns)}, found {len(actual_columns)}"
        )
        raise ValueError("Error: The loaded data doesn't match the expected column count.")

    if actual_columns != expected_columns:
        logger.error(f"Schema mismatch. Expected: {expected_columns}")
        logger.error(f"Schema mismatch. Actual:   {actual_columns}")
        raise ValueError(
            f"Schema mismatch.\nExpected: {expected_columns}\nActual:   {actual_columns}"
        )

    logger.info("Schema validation passed")
    
    
    
# create bronze table to load the raw data
def create_bronze_table(conn):
    sql = """
        CREATE TABLE IF NOT EXISTS public.bronze_sales (
            "Date"           TEXT,
            "Miti"           TEXT,
            "Inv.No"         TEXT,
            "Customer"       TEXT,
            "Product Group"  TEXT,
            "Product"        TEXT,
            "Uom"            TEXT,
            "Qty"            NUMERIC,
            "Rate"           NUMERIC,
            "B. Amount"      NUMERIC,
            "DISCOUNT"       NUMERIC,
            "VAT"            NUMERIC,
            "ROUND OFF"      NUMERIC,
            "Total Amount"   NUMERIC,
            _loaded_at       TIMESTAMP,
            _source_file     TEXT
        );
    """
    with conn.cursor() as cur:
        cur.execute(sql)

    conn.commit()
    logger.info("bronze_sales table ready")

# load data to bronze table

def load_to_bronze(conn, df):
    df = df.copy()
    df["_loaded_at"] = datetime.now()
    df["_source_file"] = "sales_data_raw.xlsx"

    # convert pandas missing values (NaN, NaT) into Python None
    df = df.astype(object).where(pd.notnull(df), None)

    insert_sql = """
        INSERT INTO public.bronze_sales (
            "Date",
            "Miti",
            "Inv.No",
            "Customer",
            "Product Group",
            "Product",
            "Uom",
            "Qty",
            "Rate",
            "B. Amount",
            "DISCOUNT",
            "VAT",
            "ROUND OFF",
            "Total Amount",
            _loaded_at,
            _source_file
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    rows = [tuple(row) for row in df.itertuples(index=False, name=None)]

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE public.bronze_sales;")
        cur.executemany(insert_sql, rows)

    conn.commit()
    logger.info(f"Loaded {len(rows)} rows into bronze_sales")

    conn.commit()
    logger.info(f"Loaded {len(rows)} rows into bronze_sales")
    
# count rows verfy insertion
def log_row_count(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM public.bronze_sales;")
        row_count = cur.fetchone()[0]

    logger.info(f"bronze_sales row count: {row_count}")

def main():
    conn = get_connection()
    logger.info("Connection established")

    try:
        df = read_raw_file()
        validate_schema(df)
    
        create_bronze_table(conn)
        load_to_bronze(conn, df)
        log_row_count(conn)
        
    finally:
        conn.close()
        logger.info("Connection closed")


if __name__ == "__main__":
    main()