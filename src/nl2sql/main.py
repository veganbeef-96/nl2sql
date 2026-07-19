from __future__ import annotations

import random
import sys

from . import console
from .config import Config, load_config
from .database import Database, DatabaseError
from .guardrail import GuardrailError
from .guardrail import enforce as enforce_department
from .llm import LLMError, Provider, make_provider

_DEPARTMENTS = ("Sales", "Marketing", "Engineering")
_NO_QUERY = "NO_QUERY"
_EXIT_COMMANDS = {"exit", "quit"}


def run(config: Config, provider: Provider, database: Database) -> None:
    department = random.choice(_DEPARTMENTS)
    console.log_info(f"Department selected: {department}")
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

        _handle_question(question, department, provider, database)


def _handle_question(
    question: str, department: str, provider: Provider, database: Database
) -> None:
    try:
        sql = provider.generate_sql(question, department)
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
        console.log_error(f"Blocked by the department guardrail: {e}")
        return

    console.print_generated_sql(guarded.sql)

    try:
        result = database.execute(guarded.sql, guarded.params)
    except DatabaseError as e:
        console.log_error(f"Query failed: {e}")
        return

    console.render_results(result)


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