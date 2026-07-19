from __future__ import annotations

from collections.abc import Collection

from rich.console import Console
from rich.table import Table

from .database import QueryResult

_console = Console()
_NULL = "—"

# Placeholder rendered in place of a redacted sensitive value.
MASK_TOKEN = "••••••"


def log_info(msg: str) -> None:
    _console.print(f"[INFO] {msg}", style="cyan", markup=False)


def log_error(msg: str) -> None:
    _console.print(f"[ERROR] {msg}", style="bold red", markup=False)


def print_banner(department: str) -> None:
    _console.print(
        f"\nAsk questions about the [bold]{department}[/bold] department's data. "
        "Type 'exit' or 'quit' (or press Ctrl-D) to leave.\n"
    )


def print_generated_sql(sql: str) -> None:
    _console.print(f"SQL: {sql}", style="dim", markup=False)


def mask_rows(
    columns: list[str],
    rows: list[tuple],
    masked_columns: Collection[str],
) -> list[tuple]:
    if not masked_columns:
        return rows

    masked_lower = {name.lower() for name in masked_columns}
    redact = [column.lower() in masked_lower for column in columns]
    if not any(redact):
        return rows

    return [
        tuple(MASK_TOKEN if redact[i] else value for i, value in enumerate(row))
        for row in rows
    ]


def render_results(
    result: QueryResult, masked_columns: Collection[str] = frozenset()
) -> None:
    if result.is_empty:
        _console.print("No results.")
        return

    rows = mask_rows(result.columns, result.rows, masked_columns)

    table = Table(show_header=True, header_style="bold")
    for column in result.columns:
        table.add_column(column)

    for row in rows:
        table.add_row(*(_format_cell(value) for value in row))

    _console.print(table)
    _console.print(f"{len(rows)} row(s).", style="dim")


def prompt_question() -> str:
    return _console.input("[bold cyan]nl2sql>[/] ").strip()


def _format_cell(value: object) -> str:
    if value is None:
        return _NULL
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)