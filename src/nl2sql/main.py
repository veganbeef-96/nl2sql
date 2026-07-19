from __future__ import annotations

import random
import sys

from collections.abc import Collection

from . import console
from .config import SENSITIVE_COLUMNS, Config, load_config
from .database import Database, DatabaseError
from .guardrail import GuardrailError
from .guardrail import enforce as enforce_department
from .llm import LLMError, Provider, make_provider

_DEPARTMENTS = ("Sales", "Marketing", "Engineering")
_NO_QUERY = "NO_QUERY"
_EXIT_COMMANDS = {"exit", "quit"}

MAX_ATTEMPTS = 2


def run(config: Config, provider: Provider, database: Database) -> None:
    department = random.choice(_DEPARTMENTS)
    console.log_info(f"Department selected: {department}")

    masked_columns = SENSITIVE_COLUMNS if config.mask_sensitive else frozenset()
    if masked_columns:
        console.log_info(
            "Sensitive column masking: ON (salary / bonus / balance redacted)."
        )

    console.print_banner(department)

    while True:
        try:
            question = console.prompt_question()
        except (EOFError, KeyboardInterrupt):
            console.log_info("Goodbye.")
            return

        if not question:
            continue
        if question.lower() in _EXIT_COMMANDS:
            console.log_info("Goodbye.")
            return

        _handle_question(question, department, provider, database, masked_columns)


def _handle_question(
    question: str,
    department: str,
    provider: Provider,
    database: Database,
    masked_columns: Collection[str] = frozenset(),
) -> None:
    feedback: str | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            sql = provider.generate_sql(question, department, feedback)
        except LLMError as e:
            console.log_error(f"Could not generate SQL: {e}")
            return


        if sql.strip() == _NO_QUERY:
            console.log_info(
                "I can't answer that from this data. Try rephrasing your question."
            )
            return

        try:
            guarded = enforce_department(sql, department)
        except GuardrailError as e:
            feedback = f"SQL: {sql}\nThe guardrail rejected it: {e}"
        else:
            console.print_generated_sql(guarded.sql)
            try:
                result = database.execute(guarded.sql, guarded.params)
            except DatabaseError as e:
                feedback = f"SQL: {sql}\nSQLite error: {e}"
            else:
                console.render_results(result, masked_columns)
                return

        if attempt < MAX_ATTEMPTS:
            console.log_info("Query failed; asking the model to correct it…")

    console.log_error(
        f"Couldn't produce a valid query for that after {MAX_ATTEMPTS} attempts."
    )


def main() -> None:
    try:
        config = load_config()
    except RuntimeError as e:
        console.log_error(str(e))
        sys.exit(1)

    try:
        database = Database(config.db_path)
    except DatabaseError as e:
        console.log_error(str(e))
        sys.exit(1)

    provider = make_provider(
        config.provider, config.api_key, config.model, config.base_url
    )
    run(config, provider, database)


if __name__ == "__main__":
    main()