from __future__ import annotations

from rich.console import Console
from rich.table import Table

from .database import QueryResult

_console = Console()
_NULL = "—"


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


def render_results(result: QueryResult) -> None:
    if result.is_empty:
        _console.print("No results.")
        return

    table = Table(show_header=True, header_style="bold")
    for column in result.columns:
        table.add_column(column)

    for row in result.rows:
        table.add_row(*(_format_cell(value) for value in row))

    _console.print(table)
    _console.print(f"{len(result.rows)} row(s).", style="dim")


def prompt_question() -> str:
    return _console.input("[bold cyan]nl2sql>[/] ").strip()


def _format_cell(value: object) -> str:
    if value is None:
        return _NULL
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)