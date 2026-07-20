# Dayforce nl2sql

This is a small console app that lets you ask questions about an employee database in plain English and get answers back. You type something like "who earns the most?" and the app has a language model turn that into SQL, runs it safely, and prints the result as a table.

The interesting part here isn't the language model. It's everything wrapped around it to keep the model honest. The app assumes the model could write anything at all, including something wrong or even malicious, so it never runs the model's SQL directly. Every query gets parsed, checked, and rewritten before it goes anywhere near the database.

## What you can do with it

- Ask questions in plain English about three tables: Employee, Certification, and Benefits.
- Stay inside your own department. When the app starts it randomly picks one department for your session (Sales, Marketing, or Engineering) and quietly makes sure every query only ever sees that department's rows. If you try to ask about another department, you just get an empty result. Nothing leaks.
- Optionally hide pay information. You can turn on a setting that blanks out the salary, bonus, and benefits balance columns in the output. Averages and other summaries still show up, so the numbers stay useful without exposing what any one person is paid.
- Get a second try when the model slips. If the generated SQL gets rejected or fails, the app hands the error back to the model and lets it fix the query once.
- Use whichever provider you like. It works with OpenAI or Anthropic, and switching between them is just a setting change.
- Trust that it can't write. The database connection is opened in read only mode, so even a query that somehow got past every check still couldn't change or delete anything.

## Setting it up

You'll need Python 3.10 or newer. From the project folder, create a virtual environment, install the dependencies, and copy the example settings file.

```sh
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install the dependencies
pip install -r requirements.txt

# 3. Set up your configuration
cp .env.example .env
#    then open .env and add the API key for whichever provider you picked
```

### The settings file (.env)

Open `.env` in your editor and fill in the values you need. Here is what each one does.

- `NL2SQL_PROVIDER`: which provider to use, either `openai` or `anthropic`. Defaults to `openai`.
- `OPENAI_API_KEY`: your OpenAI key. You need this if you are using OpenAI.
- `ANTHROPIC_API_KEY`: your Anthropic key. You need this if you are using Anthropic.
- `NL2SQL_MODEL`: the model name. Leave it blank to use the sensible default for your provider, which is `gpt-4o` for OpenAI and `claude-sonnet-5` for Anthropic.
- `OPENAI_BASE_URL` or `ANTHROPIC_BASE_URL`: optional. Set one of these if you route your requests through a gateway or a proxy.
- `NL2SQL_DB_PATH`: where the SQLite database lives. Defaults to `employees.db`.
- `NL2SQL_MASK_SENSITIVE`: set this to `1`, `true`, `yes`, or `on` if you want the pay columns blanked out in the output. It is off by default.

You only have to fill in the key for the provider you actually use. The app reads this file automatically when it starts.

Here are the two common setups. Start by copying the template with `cp .env.example .env`, then edit `.env`.

For **OpenAI**, set the provider to `openai`, paste in your OpenAI key, and pick a model.

```ini
NL2SQL_PROVIDER=openai
OPENAI_API_KEY=sk-...your real key...
NL2SQL_MODEL=gpt-4o
```

For **Anthropic**, set the provider to `anthropic`, paste in your Anthropic key, and pick a model.

```ini
NL2SQL_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...your real key...
NL2SQL_MODEL=claude-sonnet-5
```

The examples set `NL2SQL_MODEL` explicitly so you know exactly which model runs, but it is optional. Leave it blank and it falls back to the same default, which is `gpt-4o` for OpenAI and `claude-sonnet-5` for Anthropic. Everything else can stay blank too. The base URL is only for proxies, masking stays off, and you do not need a key for the provider you are not using.

## Running it

```sh
PYTHONPATH=src python -m nl2sql.main
```

When it starts, it tells you which department you have been scoped to, and whether pay masking is on, then gives you a prompt to type questions into.

```
[INFO] Department selected: Engineering
nl2sql> who has the highest salary?
SQL: SELECT Name, SalaryAmount FROM (SELECT * FROM Employee WHERE Department = :dept) AS Employee ORDER BY SalaryAmount DESC LIMIT 1
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Name         ┃ SalaryAmount ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ ...          │ 130,000.00   │
└──────────────┴──────────────┘
1 row(s).
```

That `SQL:` line under your question is the actual query the app is about to run, after the guardrail has rewritten it. It gets printed on purpose so you can see exactly what is happening. When you are done, type `exit` or `quit`, or just press `Ctrl-D`.

## Running the tests

```sh
PYTHONPATH=src pytest -o python_files="test_*.py tests_*.py" tests/
```

One quirk is worth knowing about. The database test file is named `tests_database.py`, which does not match the naming pattern pytest looks for by default. So if you just run `pytest tests/` you will get 34 of the 40 tests. The command above tells pytest to include that file too. If you would rather not think about it, you can rename the file to `test_database.py` and a plain `pytest tests/` will find everything.

The test file that matters most is `tests/test_guardrail.py`. It runs against the real database and proves the promises that count. You only ever see your own department, nothing leaks across departments, and every attempt to write, drop, or otherwise change data gets rejected.

## How it is put together

The code is split into small modules so each piece does one job and can be tested on its own. Swapping the language model provider, for example, only touches a single file.

- `config.py` loads and checks your settings from the environment.
- `schema.py` builds the prompt that describes the tables to the model, along with a few worked examples.
- `llm.py` wraps the two providers behind one common interface.
- `guardrail.py` is the security core. It parses, checks, and rewrites the SQL.
- `database.py` talks to SQLite in read only mode and hands back the results.
- `console.py` handles everything you see on screen, including the result tables and the pay masking.
- `main.py` runs the loop that ties it all together.

### What happens to a question

Here is the path a question takes from the moment you hit enter.

1. The model reads your question and writes a raw SQL query. If your question cannot be answered from these three tables, it returns a special `NO_QUERY` signal, and the app simply tells you it cannot help with that one.
2. The guardrail takes over. This is the trust boundary, and it is strict. It rejects anything that is not a single read query. It only allows `SELECT` and set operations like `UNION`. It refuses any query that tries to write, drop, or run a command. It only allows the three known tables. Then it rewrites the query so that every table is filtered down to your department.
3. The rewritten query runs against the read only database connection.
4. The results come back and get printed as a table, with the pay columns blanked out if you turned that on.

If the guardrail rejects the query, or the database throws an error, the app does not give up right away. It sends the error back to the model and lets it try once more. If the second attempt also fails, you get a clear message and can just ask something else. A single bad question never crashes the session.

### The two layers that keep data safe

The whole design rests on one idea. Never trust what the model writes. Access is enforced by the code, not by asking the model nicely. There are two layers, plus a final safety net.

**Keeps you in your department.** The guardrail rewrites every table in your query into a filtered version scoped to your department. In practice it turns a plain reference to a table into something like this.

```sql
Employee        (SELECT * FROM Employee WHERE Department = :dept)

Certification   (SELECT * FROM Certification
                   WHERE EmployeeId IN
                     (SELECT EmployeeId FROM Employee WHERE Department = :dept))
```

Benefits follows the same idea, linked back to Employee through the EmployeeId foreign key. Because the department filter is always applied at the base, anything the model adds on top can only narrow the results further. It can never widen them. Ask for a different department and you get nothing back. The department name is passed in as a bound parameter, never glued into the query as text, so there is no room for injection there either.

**Sensitive-column masking.** Set `NL2SQL_MASK_SENSITIVE=true` to redact raw compensation values
(`SalaryAmount`, `YearlyBonusAmount`, `RemainingBalance`) in the output. It matches
on the exact column name, so an individual's salary is hidden while an aggregate
like `AVG(SalaryAmount) AS avg_salary` still shows, the same way HR systems let
people see summary figures without exposing anyone's paycheck. It is off by default
so results are fully visible during evaluation. Where the guardrail is row-level,
this is a column-level layer on top of it.

**The safety net.** On top of both layers, the database connection itself is opened in read only mode, using the SQLite URI `file:{path}?mode=ro`. Even if a query somehow got past every check, SQLite physically would not let it write or change anything.

A couple of limits exist on purpose.

- The guardrail rejects `WITH` clauses, also known as CTEs. Supporting them safely would take extra work to stop a query from disguising a forbidden table under a friendly name, and nothing here needs them.
- Masking only affects what you see. The values are still read from the database before they get blanked out. That is fine for a single user console tool like this one. If you needed stricter control, you would drop the columns in the SQL itself.

## Notes on the AI side

### How the model is used

The model has a deliberately small job. All it does is turn your question into a single SQLite `SELECT`. It has no access to the database and it cannot run anything. It just produces text, and the guardrail decides whether that text ever runs.

The prompt, which is built in `schema.py`, gives the model a compact description of the tables. That covers the columns, their types, the units, how the tables relate to each other, and which fields can be empty. It also includes a handful of example questions and answers so the model learns the shape we want. That shape is one `SELECT`, plain SQLite, no explanation, and no markdown. On purpose, none of the examples filter by department, because that is the guardrail's job. The prompt even tells the model that access is already scoped, so it does not bother adding its own department filter. If a question cannot be answered from these tables, the model replies with `NO_QUERY`.

The app is also forgiving about formatting. If the model wraps its answer in code fences, those get stripped off. If it sends back nothing useful, that becomes a clean error rather than a crash.

And when something does go wrong, the exact error gets folded into the next prompt so the model can see what it did wrong and correct it. `NO_QUERY` is treated as a final answer, though, so the app does not retry those.

### Switching providers

Both providers sit behind one small common interface, so choosing between OpenAI and Anthropic comes down to a single setting. A couple of practical details are worth calling out.

- The provider SDKs are only imported when you actually use them, so you do not need both packages installed. You only need the one you are using.
- The requests are kept deliberately minimal so that gateways and newer models do not reject them. For OpenAI the app sends only the model and the messages. For Anthropic it leaves out temperature and turns off thinking.

The default models are `gpt-4o` for OpenAI and `claude-sonnet-5` for Anthropic. You can point `NL2SQL_MODEL` at something else if you want. One thing to watch is that the Anthropic path turns thinking off, so if you switch to a model that always thinks, you will want to pick a compatible model or adjust `llm.py`.

## Built with AI tooling

This project was developed with Claude Code, and the way it was built matters as much as the result. It was delivered as a series of small, self contained steps rather than one large drop, and every step shipped together with the tests that prove it works. A reviewer can check all of this directly against the git history and the test suite.

- **Small, reviewable changes.** The history is a clean set of Conventional Commits, one logical change each: the read only database layer, then the guardrail, then the language model layer, the console, the retry loop, and finally the pay masking. Each commit is the size and shape of a good pull request, which keeps every step easy to review and easy to trust.
- **Tests grew with the code.** There are 40 tests in total, and they were written alongside each feature rather than bolted on afterward. The security core alone has 28 tests that run against the real database, and each layer was proven green before the next one was built on top of it. This is what made fast iteration safe.
- **Refactoring on a safety net.** When the retry loop was added, it reshaped the question handling into a bounded attempt loop while the existing suite guarded against regressions. When masking was added, it introduced a whole new column access layer without breaking any of the tests already in place.
- **Debugging with the tools, not guesswork.** Two real examples from the build: a config value that read as on when it should have been off was traced back to the on disk `.env` being loaded, and confirmed by re running the check in a clean directory. Separately, the test runner finding 34 of 40 tests was root caused to a file naming pattern. In both cases the loop was observe, form a hypothesis, verify, then apply a targeted fix.

The conventions, security invariants, and commit rules that came out of this are written down in `CLAUDE.md`, so the same standard carries forward whether the next change is made by a person or an AI assistant.
