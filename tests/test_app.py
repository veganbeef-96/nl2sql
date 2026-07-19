from pathlib import Path

from nl2sql import main
from nl2sql.config import SENSITIVE_COLUMNS
from nl2sql.console import MASK_TOKEN, mask_rows
from nl2sql.database import Database

DB_PATH = Path(__file__).resolve().parent.parent / "employees.db"


class StubProvider:
    """Returns a scripted SQL string per call and records the feedback it got."""

    def __init__(self, replies: list[str]):
        self._replies = replies
        self.calls = 0
        self.feedbacks: list[str | None] = []

    def generate_sql(self, question: str, department: str, feedback=None) -> str:
        self.feedbacks.append(feedback)
        reply = self._replies[self.calls]
        self.calls += 1
        return reply


def test_retry_after_guardrail_rejection():
    provider = StubProvider(
        ["DROP TABLE Employee", "SELECT Name FROM Employee LIMIT 1"]
    )
    database = Database(str(DB_PATH))

    main._handle_question("who works here", "Sales", provider, database)

    assert provider.calls == 2
    assert provider.feedbacks[0] is None
    assert provider.feedbacks[1] is not None
    assert "DROP TABLE Employee" in provider.feedbacks[1]


def test_no_query_does_not_retry():
    provider = StubProvider(["NO_QUERY", "SELECT 1"])
    database = Database(str(DB_PATH))

    main._handle_question("what's the weather", "Sales", provider, database)

    assert provider.calls == 1
    assert provider.feedbacks == [None]


def test_success_on_first_attempt_does_not_retry():
    provider = StubProvider(["SELECT Name FROM Employee LIMIT 1"])
    database = Database(str(DB_PATH))

    main._handle_question("who works here", "Sales", provider, database)

    assert provider.calls == 1
    assert provider.feedbacks == [None]

def test_mask_rows_redacts_raw_sensitive_column():
    columns = ["Name", "SalaryAmount"]
    rows = [("Alice", 100000.0), ("Bob", 90000.0)]

    masked = mask_rows(columns, rows, SENSITIVE_COLUMNS)

    assert masked == [("Alice", MASK_TOKEN), ("Bob", MASK_TOKEN)]
    assert rows == [("Alice", 100000.0), ("Bob", 90000.0)]


def test_mask_rows_leaves_aggregate_alias_visible():
    columns = ["Department", "avg_salary"]
    rows = [("Sales", 82500.0)]

    masked = mask_rows(columns, rows, SENSITIVE_COLUMNS)

    assert masked == [("Sales", 82500.0)]


def test_mask_rows_is_noop_when_no_masked_columns():
    columns = ["Name", "SalaryAmount"]
    rows = [("Alice", 100000.0)]

    masked = mask_rows(columns, rows, frozenset())

    assert masked is rows