from __future__ import annotations

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

_ALLOWED_TABLES: dict[str, str] = {
    "employee": "Employee",
    "certification": "Certification",
    "benefits": "Benefits",
}

_DEPT_FILTER_SQL: dict[str, str] = {
    "employee": "(SELECT * FROM Employee WHERE Department = :dept)",
    "certification": (
        "(SELECT * FROM Certification WHERE EmployeeId IN "
        "(SELECT EmployeeId FROM Employee WHERE Department = :dept))"
    ),
    "benefits": (
        "(SELECT * FROM Benefits WHERE EmployeeId IN "
        "(SELECT EmployeeId FROM Employee WHERE Department = :dept))"
    ),
}

_DISALLOWED_NODE_TYPES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Attach,
    exp.Pragma,
    exp.Command,
    exp.Transaction,
)

_READ_ONLY_TOP_LEVEL: tuple[type[exp.Expression], ...] = (
    exp.Select,
    exp.Union,
    exp.Intersect,
    exp.Except,
)

_DIALECT = "sqlite"


class GuardrailError(Exception):
    """Raised when SQL fails a guardrail check (write, disallowed table, etc.)."""


@dataclass
class GuardedQuery:
    sql: str
    params: dict = field(default_factory=dict)


def enforce(sql: str, department: str) -> GuardedQuery:
    statement = _parse_single_statement(sql)
    _check_read_only(statement)
    _check_no_disallowed_nodes(statement)
    _check_no_cte(statement)
    rewritten = _rewrite_tables(statement)
    return GuardedQuery(sql=rewritten.sql(dialect=_DIALECT), params={"dept": department})


def _parse_single_statement(sql: str) -> exp.Expression:
    try:
        statements = [s for s in sqlglot.parse(sql, read=_DIALECT) if s is not None]
    except sqlglot.errors.SqlglotError as e:
        raise GuardrailError(f"Could not parse SQL: {e}") from e

    if len(statements) != 1:
        raise GuardrailError(
            f"Expected exactly one SQL statement, got {len(statements)}"
        )
    return statements[0]


def _check_read_only(statement: exp.Expression) -> None:
    if not isinstance(statement, _READ_ONLY_TOP_LEVEL):
        raise GuardrailError(
            f"Only SELECT queries are allowed, got {type(statement).__name__}"
        )


def _check_no_disallowed_nodes(statement: exp.Expression) -> None:
    for node in statement.walk():
        if isinstance(node, _DISALLOWED_NODE_TYPES):
            raise GuardrailError(
                f"Disallowed statement type in query: {type(node).__name__}"
            )


def _check_no_cte(statement: exp.Expression) -> None:
    if statement.find(exp.With) is not None:
        raise GuardrailError("WITH / CTE queries are not supported")


def _rewrite_tables(statement: exp.Expression) -> exp.Expression:
    tables = list(statement.find_all(exp.Table))

    for table in tables:
        key = table.name.lower()
        if key not in _ALLOWED_TABLES:
            raise GuardrailError(
                f"Query references a table outside the allowlist: {table.name!r}"
            )

    for table in tables:
        key = table.name.lower()
        alias_name = table.alias or table.name
        replacement = sqlglot.parse_one(_DEPT_FILTER_SQL[key], read=_DIALECT)
        replacement.set("alias", exp.TableAlias(this=exp.to_identifier(alias_name)))
        table.replace(replacement)

    return statement