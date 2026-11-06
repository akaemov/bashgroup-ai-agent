"""Read server-side database settings without exposing passwords in command lines."""
import json
import os
from pathlib import Path

from sqlalchemy import URL


def settings():
    path = Path(os.environ.get("BASHGROUP_DB_CONFIG", "/etc/bashgroup/database.json"))
    return json.loads(path.read_text())


def database_url(purpose="app"):
    config = settings()
    account = config[purpose]
    return URL.create(
        "postgresql+psycopg",
        username=account["user"],
        password=account["password"],
        host=config["host"],
        port=config["port"],
        database=config["database"],
    )
