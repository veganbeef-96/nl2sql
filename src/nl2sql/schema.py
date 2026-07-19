from __future__ import annotations

_SCHEMA_DESCRIPTION = """\
Tables (SQLite):

Employee
  EmployeeId          INTEGER  primary key
  Name                TEXT
  Department          TEXT     (e.g. 'Sales', 'Marketing', 'Engineering')
  Role                TEXT     job title, e.g. 'Software Engineer'
  EmploymentStartDate TEXT     ISO-8601 date, 'YYYY-MM-DD'
  SalaryAmount        REAL     annual salary, in dollars
  YearlyBonusAmount   REAL     annual bonus in dollars; may be NULL

Certification
  CertificationId     INTEGER  primary key
  EmployeeId          INTEGER  -> Employee.EmployeeId
  CertificationName   TEXT     e.g. 'AWS Certified Solutions Architect'
  DateAchieved        TEXT     ISO-8601 date, 'YYYY-MM-DD'

Benefits
  BenefitId           INTEGER  primary key
  EmployeeId          INTEGER  -> Employee.EmployeeId
  BenefitsPackage     TEXT     e.g. 'Gold', 'Silver'
  RemainingBalance    REAL     dollars remaining in the package
"""

_FEW_SHOT_EXAMPLES = """\
Examples:

Q: Who are the software engineers?
A: SELECT Name FROM Employee WHERE Role = 'Software Engineer'

Q: Which employees hold an AWS certification?
A: SELECT Employee.Name, Certification.CertificationName
   FROM Employee JOIN Certification ON Certification.EmployeeId = Employee.EmployeeId
   WHERE Certification.CertificationName LIKE '%AWS%'

Q: What is the average salary?
A: SELECT AVG(SalaryAmount) FROM Employee

Q: Who has the highest remaining benefits balance?
A: SELECT Employee.Name, Benefits.RemainingBalance
   FROM Employee JOIN Benefits ON Benefits.EmployeeId = Employee.EmployeeId
   ORDER BY Benefits.RemainingBalance DESC
   LIMIT 1
"""


def build_system_prompt(department: str) -> str:
    """Assemble the system prompt for generating SQL scoped to `department`."""
    return f"""\
You translate natural-language questions into a single SQLite SQL query.

{_SCHEMA_DESCRIPTION}
{_FEW_SHOT_EXAMPLES}
The user belongs to the {department} department. Access is automatically
restricted to that department's data — do NOT add any WHERE clause that filters
on Department. Write the query as if it ran over the whole company.

Rules:
- Output exactly ONE SELECT statement.
- Use only the tables Employee, Certification, and Benefits.
- Use standard SQLite syntax.
- Return ONLY the SQL — no explanation, no comments, no markdown code fences.
- If the question cannot be answered from these tables, return exactly NO_QUERY.
"""