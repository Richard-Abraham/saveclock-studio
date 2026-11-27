"""The `saveclock` command-line tool: a thin client of the REST API (ARCH §2, plan 009).

It may import only the standard library, httpx, pydantic and `saveclock.config` (an import-linter
contract enforces it): no business logic lives here, and a rule the API owns is never copied.
"""

__version__ = "0.1.0"
