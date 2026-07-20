# CLAUDE.md

Guidance for Claude Code (and any developer) working in this repository. Read this before making changes.

## What this project is

A natural-language-to-SQL console app over a small SQLite employee database. A user asks a question in plain English, an LLM generates SQL, a deterministic guardrail rewrites that SQL so it can only read the user's assigned department, and the query runs against a read-only connection.

The security layering is the point of the project, not the LLM. The model is treated as untrusted. Its output is never executed directly.

## Golden rules (do not break these)

1. **All model-generated SQL must pass through `guardrail.enforce()` before it reaches the database.** Never call `database.execute()` on raw LLM output. The guardrail is the trust boundary.
2. **The database connection stays read-only** (`file:{path}?mode=ro`). Do not change the open mode or add a writable path.
3. **The department is always a bound parameter** (`:dept`), never string-interpolated into SQL.
4. **The guardrail allowlist is exactly `{Employee, Certification, Benefits}`.** Adding a table means updating both the allowlist and its department-scoping rewrite in `guardrail.py`.
5. **Never commit secrets.** `.env` is gitignored. Only `.env.example` (with empty values) is tracked.
6. **Run the full test suite before committing.** The guardrail tests are the safety contract for the whole app.

## Commands

```sh
# One-time setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then add your provider API key

# Run the app
PYTHONPATH=src python -m nl2sql.main

# Run the full test suite (all 40 tests)
PYTHONPATH=src pytest -o python_files="test_*.py tests_*.py" tests/

# Run only the critical guardrail suite while iterating on security
PYTHONPATH=src pytest tests/test_guardrail.py -v
```

There is no packaging config yet, so `PYTHONPATH=src` is required for both running and testing.

## Project structure

```
dayforce-nl2sql/
├── CLAUDE.md            This file
├── README.md           User-facing docs
├── requirements.txt    Runtime and test dependencies
├── .env.example        Config template (tracked; real .env is gitignored)
├── employees.db        SQLite fixture (Employee / Certification / Benefits)
├── src/nl2sql/
│   ├── __init__.py     Package marker and __version__
│   ├── config.py       Load and validate env config; SENSITIVE_COLUMNS constant
│   ├── schema.py       Build the system prompt (schema + few-shot + rules)
│   ├── llm.py          Provider protocol, OpenAI/Anthropic providers, factory
│   ├── guardrail.py    SECURITY CORE: parse, validate, rewrite SQL (sqlglot)
│   ├── database.py     Read-only SQLite layer, QueryResult, DatabaseError
│   ├── console.py      rich presentation, pure mask_rows(), logging helpers
│   └── main.py         Agent loop and entry point
└── tests/
    ├── tests_database.py   Read-only access and schema tests
    ├── test_guardrail.py   The critical suite: scoping, no leaks, rejections
    └── test_app.py         Retry loop and column-masking tests
```

Each module owns one concern and one custom exception where relevant (`DatabaseError`, `GuardrailError`, `LLMError`). This keeps every layer testable in isolation and makes a vendor swap a one-class change.

## Request flow

```
question
  -> llm.generate_sql(question, department[, feedback])   model writes raw SQL
       -> "NO_QUERY" short-circuits to a clean message (never retried)
  -> guardrail.enforce(sql, department)                   the trust boundary
       single statement only; SELECT/UNION/INTERSECT/EXCEPT only;
       no write/DDL/command nodes; allowlisted tables only;
       every table rewritten to a :dept-filtered subquery
  -> database.execute(guarded.sql, {"dept": department})  read-only connection
  -> console.render_results(result, masked_columns)       optional pay masking
```

On a `GuardrailError` or `DatabaseError`, the failure is fed back to the model for exactly one retry (`MAX_ATTEMPTS = 2` in `main.py`). A second failure surfaces a clean message. One bad question never crashes the loop.

## Security model (the invariants in detail)

- **Row-level (department).** `guardrail.py` collects every `Table` node and replaces each with a department-scoped subquery. `Employee` filters on `Department = :dept`; `Certification` and `Benefits` scope through `EmployeeId IN (SELECT EmployeeId FROM Employee WHERE Department = :dept)`. Because the filter is applied at the base table, any predicate the model adds can only narrow further, never widen. A cross-department request returns empty, not a leak.
- **CTEs are rejected by design.** `WITH` clauses are refused because supporting them safely would require per-scope name resolution to block a table-shadowing attack. Do not add CTE support without solving that first.
- **Column-level (masking).** `console.mask_rows()` is a pure function that redacts result columns matching `SENSITIVE_COLUMNS` by exact, case-insensitive name. This is display-time only. It is intentionally weaker than the row-level guardrail (an aliased column such as `SalaryAmount AS pay` defeats it). If stronger column control is ever required, enforce it in the guardrail/SQL layer, not at render time.
- **Read-only backstop.** `database.py` opens `file:{path}?mode=ro`. This is the last line of defense if anything ever slipped past the guardrail.

## Coding conventions

- Target Python 3.10+. Every module starts with `from __future__ import annotations` and uses PEP 604 unions (`str | None`) in type hints.
- Use dataclasses for value objects (`Config` is `frozen=True`, `QueryResult`, `GuardedQuery`).
- One custom exception per layer; wrap third-party errors (sqlite3, SDK) so callers get a clean message, never a raw traceback.
- Import provider SDKs lazily inside the provider method, so only the selected provider's package is required at runtime.
- Keep presentation logic pure and side-effect free where possible (`mask_rows` returns new rows and never mutates its input).
- Prefix private helpers with `_`. Add short docstrings to public functions and any non-obvious helper.
- Match the surrounding style: small functions, explicit names, minimal comments that explain the why (especially around security decisions).

## Testing conventions

- Tests run against the real `employees.db` through the read-only `Database` layer, so they exercise actual query behavior, not mocks.
- **Naming quirk:** `tests/tests_database.py` does not match pytest's default `test_*.py` pattern, so a bare `pytest tests/` finds 34 of 40 tests. Always use the `-o python_files="test_*.py tests_*.py"` override (see Commands) or rename the file if you want plain discovery.
- `tests/test_guardrail.py` is the contract for the security core: department scoping, no cross-department leakage, and rejection of every write, DDL, command, multi-statement, and non-allowlisted table. Any change to `guardrail.py` must keep this suite green, and new guardrail behavior needs a new test here.
- Use `StubProvider` (in `test_app.py`) to drive the loop without network calls when testing orchestration.

## How to extend common things

- **Add an LLM provider:** implement the `Provider` protocol (`generate_sql(question, department, feedback=None) -> str`) as a new class with a lazy SDK import, register it in `make_provider()`, and add its key/base-url/default-model entries in `config.py`. Reuse `_strip_sql_fences` / `_require_sql`.
- **Add a sensitive column:** add the column name to `SENSITIVE_COLUMNS` in `config.py`. Masking picks it up automatically.
- **Change retry behavior:** adjust `MAX_ATTEMPTS` in `main.py`. Keep `NO_QUERY` non-retryable.
- **Add a table to the schema:** update `_ALLOWED_TABLES` and `_DEPT_FILTER_SQL` in `guardrail.py` (with a correct department-scoping rewrite), describe it in `schema.py`, and add guardrail tests proving it scopes correctly and cannot leak.

## Development workflow (built with Claude Code)

This repository was built with Claude Code, and new work should follow the same approach. This workflow is what keeps delivery fast without sacrificing quality.

- **Ship in small, self-contained steps.** One concern per commit, each with the tests that prove it. The history reflects this: read-only DB layer, then guardrail, then LLM layer, console, retry, and masking. Keep new work the same size and shape so each change stays reviewable.
- **Write tests with the feature, not after.** Every layer landed with its own suite and was green before the next layer was built on top of it. New behavior needs a matching test in the same change. There are 40 tests today, 28 of them on the guardrail.
- **Verify library behavior before relying on it, especially in security code.** The guardrail was written only after probing how sqlglot parses statements, classifies write and DDL nodes, and preserves table aliases. Do not guess an AST shape or an API contract. Confirm it against the real library, then build on the confirmed behavior.
- **Refactor behind a green suite.** Treat the existing tests as the safety net. Run the full suite before and after a refactor, and add tests for any new behavior the refactor introduces.
- **Debug methodically.** Observe the actual output or error, form a specific hypothesis, verify it in isolation, then apply a targeted fix. Two worked examples from this build: a config value that read as enabled when it should have been off was traced to `load_dotenv` reading the on-disk `.env`, and confirmed by re-running in a directory with no `.env`. A test count of 34 rather than 40 was traced to `tests_database.py` not matching pytest's default discovery pattern. In both cases the fix followed the diagnosis rather than a guess.

## Git and commit rules

This repo follows Conventional Commits, matching the existing history.

- **Format:** `type: short imperative summary`, lowercase, no trailing period. Keep the summary under about 72 characters.
- **Types used here:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
- **Examples from this repo:**
  - `feat: add department guardrail with sqlglot row level security`
  - `feat: add llm provider with openai and anthropic`
  - `feat: add column-level masking of sensitive fields`
- **One logical change per commit.** Do not mix a feature and an unrelated refactor.
- **Tests must pass before you commit.** Security-relevant changes must keep `test_guardrail.py` green.
- **Never stage `.env`, real API keys, or any secret.** Review `git status` after a broad `git add`, and inspect any unexpected file before committing.
- **Branch off `main`** for non-trivial work rather than committing directly to it. Commit or push only when the user asks.
- **Claude Code commits** end the message with the trailer:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

## Gotchas to remember

- `PYTHONPATH=src` is required everywhere until packaging is added.
- The Anthropic provider disables thinking. Switching `NL2SQL_MODEL` to a model that requires thinking always on (for example a Fable-tier model) will error. Pick a compatible model or adjust `llm.py`.
- `load_dotenv()` reads the on-disk `.env`, so local env-var experiments can be shadowed by whatever `.env` contains. Test config parsing in a directory without a `.env` if you need a clean baseline.
- Masking hides values at display time only. The data is still read from the database first. Do not describe it as true access control.
