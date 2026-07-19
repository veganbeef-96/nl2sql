from pathlib import Path

import pytest

from nl2sql.database import Database
from nl2sql.guardrail import GuardedQuery, GuardrailError, enforce

DB_PATH = Path(__file__).resolve().parent.parent / "employees.db"
DEPARTMENTS = ["Sales", "Marketing", "Engineering"]


@pytest.fixture
def db() -> Database:
    return Database(str(DB_PATH))


def run(db: Database, sql: str, department: str):
    guarded: GuardedQuery = enforce(sql, department)
    return db.execute(guarded.sql, guarded.params)

@pytest.mark.parametrize("department", DEPARTMENTS)
def test_plain_query_returns_only_selected_department(db: Database, department: str):
    result = run(db, "SELECT * FROM Employee", department)
    assert not result.is_empty

    dept_col = result.columns.index("Department")
    assert all(row[dept_col] == department for row in result.rows)


@pytest.mark.parametrize("department", DEPARTMENTS)
def test_explicit_other_department_predicate_returns_empty(db: Database, department: str):
    other = next(d for d in DEPARTMENTS if d != department)
    result = run(db, f"SELECT * FROM Employee WHERE Department = '{other}'", department)
    assert result.is_empty


@pytest.mark.parametrize("department", DEPARTMENTS)
def test_union_across_departments_stays_scoped(db: Database, department: str):
    sql = " UNION ".join(
        f"SELECT * FROM Employee WHERE Department = '{d}'" for d in DEPARTMENTS
    )
    result = run(db, sql, department)
    assert not result.is_empty

    dept_col = result.columns.index("Department")
    assert all(row[dept_col] == department for row in result.rows)


@pytest.mark.parametrize("department", DEPARTMENTS)
def test_join_to_certification_only_returns_selected_dept(db: Database, department: str):
    sql = (
        "SELECT Employee.Name, Certification.CertificationName "
        "FROM Employee JOIN Certification "
        "ON Certification.EmployeeId = Employee.EmployeeId"
    )
    result = run(db, sql, department)

    expected = db.execute(
        "SELECT Employee.Name, Certification.CertificationName "
        "FROM Employee JOIN Certification "
        "ON Certification.EmployeeId = Employee.EmployeeId "
        "WHERE Employee.Department = ?",
        (department,),
    )
    assert set(result.rows) == set(expected.rows)
    assert not expected.is_empty 
    
REJECTED_SQL = [
    ("drop", "DROP TABLE Employee"),
    ("delete", "DELETE FROM Employee"),
    ("update", "UPDATE Employee SET SalaryAmount = 0"),
    ("insert", "INSERT INTO Employee (EmployeeId, Name, Department, Role, EmploymentStartDate, SalaryAmount) VALUES (999, 'X', 'Sales', 'Y', '2024-01-01', 1)"),
    ("pragma", "PRAGMA table_info(Employee)"),
    ("attach", "ATTACH DATABASE 'evil.db' AS evil"),
    ("create", "CREATE TABLE evil (a INT)"),
    ("multi_statement", "SELECT 1; DROP TABLE Employee"),
    ("sqlite_master", "SELECT * FROM sqlite_master"),
    ("pragma_table_function", "SELECT * FROM pragma_table_info('Employee')"),
    ("made_up_table", "SELECT * FROM NotARealTable"),
]


@pytest.mark.parametrize("name, sql", REJECTED_SQL, ids=[n for n, _ in REJECTED_SQL])
def test_rejected_sql_raises_guardrail_error(name: str, sql: str):
    with pytest.raises(GuardrailError):
        enforce(sql, "Sales")


def test_unparseable_sql_is_rejected():
    with pytest.raises(GuardrailError):
        enforce("this is not sql at all !!!", "Sales")

def test_department_filter_is_injected_when_absent():
    guarded = enforce("SELECT * FROM Employee", "Engineering")
    assert "WHERE Department = :dept" in guarded.sql
    assert guarded.params == {"dept": "Engineering"}


def test_alias_is_preserved_through_rewrite():
    guarded = enforce("SELECT e.Name FROM Employee e", "Engineering")
    assert "AS e" in guarded.sql
    assert "e.Name" in guarded.sql or "e" in guarded.sql


def test_unaliased_table_keeps_its_name_as_alias():
    guarded = enforce("SELECT Employee.Name FROM Employee", "Engineering")
    assert "AS Employee" in guarded.sql
    assert "Employee.Name" in guarded.sql


def test_related_tables_scoped_through_employee_id():
    guarded = enforce("SELECT * FROM Certification", "Engineering")
    assert "EmployeeId IN" in guarded.sql
    assert "FROM Employee WHERE Department = :dept" in guarded.sql

    guarded_benefits = enforce("SELECT * FROM Benefits", "Engineering")
    assert "EmployeeId IN" in guarded_benefits.sql
    assert "FROM Employee WHERE Department = :dept" in guarded_benefits.sql