import sqlite3
from pathlib import Path

import pytest

from nl2sql.database import Database, DatabaseError

DB_PATH = Path(__file__).resolve().parent.parent / "employees.db"


@pytest.fixture
def db() -> Database:
    return Database(str(DB_PATH))


def test_select_returns_expected_columns_and_rows(db: Database):
    result = db.execute("SELECT EmployeeId, Name FROM Employee ORDER BY EmployeeId LIMIT 1")
    assert result.columns == ["EmployeeId", "Name"]
    assert len(result.rows) == 1
    assert isinstance(result.rows[0], tuple)
    assert len(result.rows[0]) == 2


def test_empty_result_sets_is_empty(db: Database):
    result = db.execute("SELECT * FROM Employee WHERE EmployeeId = -1")
    assert result.is_empty is True
    assert result.rows == []


def test_non_empty_result_is_not_empty(db: Database):
    result = db.execute("SELECT * FROM Employee LIMIT 1")
    assert result.is_empty is False


def test_write_is_rejected_by_readonly_connection(db: Database):
    with pytest.raises(DatabaseError):
        db.execute("UPDATE Employee SET SalaryAmount = 0")


def test_missing_db_file_raises_clean_error(tmp_path):
    missing = tmp_path / "does_not_exist.db"
    with pytest.raises(DatabaseError):
        Database(str(missing))


def test_schema_text_lists_expected_tables(db: Database):
    schema = db.schema_text()
    assert "Employee" in schema
    assert "Certification" in schema
    assert "Benefits" in schema
