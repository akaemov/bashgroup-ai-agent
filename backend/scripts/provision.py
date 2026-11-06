"""One-time root bootstrap. No passwords are printed or passed as CLI arguments."""
import json
import os
from pathlib import Path
import secrets
import subprocess

from psycopg import sql


def admin(statement, database="postgres"):
    result = subprocess.run(
        ["runuser", "-u", "postgres", "--", "psql", "-X", "-v", "ON_ERROR_STOP=1", "-At", "-d", database],
        input=statement, text=True, capture_output=True,
    )
    if result.returncode:
        # SQL error output may include a password-bearing statement. Do not echo it.
        raise RuntimeError(f"PostgreSQL bootstrap failed in {database}; review locally")
    return result.stdout.strip()


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run as root")
    path = Path("/etc/bashgroup/database.json")
    if path.exists():
        raise SystemExit("Existing credentials found. Bootstrap is one-time; use migrations for upgrades.")
    occupied = admin("SELECT count(*) FROM pg_roles WHERE rolname IN ('bashgroup_app','bashgroup_migrator','bashgroup_owner')")
    if occupied != "0" or admin("SELECT count(*) FROM pg_database WHERE datname='bashgroup'") != "0":
        raise SystemExit("Database/role name collision. Inspect before provisioning.")
    config = {
        "host": "127.0.0.1", "port": 5432, "database": "bashgroup",
        "app": {"user": "bashgroup_app", "password": secrets.token_urlsafe(40)},
        "migrator": {"user": "bashgroup_migrator", "password": secrets.token_urlsafe(40)},
    }
    # Persist first, with O_EXCL, so credentials survive a partial bootstrap failure.
    path.parent.mkdir(mode=0o700, exist_ok=True)
    path.parent.chmod(0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(config, stream, indent=2)
        stream.write("\n")
    statements = ["BEGIN;", "CREATE ROLE bashgroup_owner NOLOGIN;"]
    for purpose in ("app", "migrator"):
        account = config[purpose]
        statements.append(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {};").format(
            sql.Identifier(account["user"]), sql.Literal(account["password"])
        ).as_string())
    statements.extend(["GRANT bashgroup_owner TO bashgroup_migrator;", "COMMIT;"])
    admin("\n".join(statements))
    admin("CREATE DATABASE bashgroup OWNER postgres ENCODING 'UTF8' TEMPLATE template0;")
    admin("""
        REVOKE ALL ON DATABASE bashgroup FROM PUBLIC;
        GRANT CONNECT ON DATABASE bashgroup TO bashgroup_app, bashgroup_migrator;
        ALTER DATABASE bashgroup SET timezone = 'UTC';
        REVOKE CREATE ON SCHEMA public FROM PUBLIC;
        CREATE SCHEMA app AUTHORIZATION bashgroup_owner;
        GRANT USAGE ON SCHEMA app TO bashgroup_app;
        ALTER DEFAULT PRIVILEGES FOR ROLE bashgroup_owner IN SCHEMA app
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bashgroup_app;
        ALTER DEFAULT PRIVILEGES FOR ROLE bashgroup_owner IN SCHEMA app
            GRANT USAGE, SELECT ON SEQUENCES TO bashgroup_app;
        ALTER ROLE bashgroup_app IN DATABASE bashgroup SET search_path = app, pg_catalog;
        ALTER ROLE bashgroup_migrator IN DATABASE bashgroup SET search_path = app, pg_catalog;
        ALTER ROLE bashgroup_app SET statement_timeout = '30s';
        ALTER ROLE bashgroup_app SET idle_in_transaction_session_timeout = '60s';
    """, "bashgroup")
    print("Database, roles and protected credentials created. Apply Alembic migrations next.")


if __name__ == "__main__":
    main()
