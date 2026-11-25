"""`python -m saveclock.api.export`: print the OpenAPI document, deterministically.

Uses obviously fake settings: building the app connects to nothing and needs no environment.
"""

import json

from saveclock.config import Settings
from saveclock.main import create_app


def openapi_json() -> str:
    settings = Settings(
        app_env="ci",
        app_origin="http://localhost:3000",
        database_url="postgresql+asyncpg://export:export@localhost/export",
        redis_url="redis://localhost:6379/0",
        blob_root="/nonexistent",
    )
    return json.dumps(create_app(settings).openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    print(openapi_json(), end="")
