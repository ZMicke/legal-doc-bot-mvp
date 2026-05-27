import time

from sqlalchemy.exc import OperationalError
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.database.models import ClaimRequest, Document
from app.database.session import Base


def ensure_database_schema(engine: Engine, retries: int = 20, delay_seconds: int = 2) -> None:
    last_error = None

    for _ in range(retries):
        try:
            Base.metadata.create_all(bind=engine)
            break
        except OperationalError as error:
            last_error = error
            time.sleep(delay_seconds)
    else:
        raise last_error

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    if Document.__tablename__ not in table_names or ClaimRequest.__tablename__ not in table_names:
        Base.metadata.create_all(bind=engine)
        inspector = inspect(engine)

    claim_columns = {
        column["name"]
        for column in inspector.get_columns(ClaimRequest.__tablename__)
    }

    missing_columns = []

    if "docx_path" not in claim_columns:
        missing_columns.append("ADD COLUMN docx_path VARCHAR")

    if "trace_json" not in claim_columns:
        missing_columns.append("ADD COLUMN trace_json TEXT")

    if missing_columns:
        with engine.begin() as connection:
            for statement in missing_columns:
                connection.execute(text(f"ALTER TABLE claim_requests {statement}"))
