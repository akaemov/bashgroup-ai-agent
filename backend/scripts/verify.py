"""Integration checks against PostgreSQL; runtime writes always rolled back.

Restore verification creates and drops only a uniquely named disposable database.
Run as root on the VPS, with a fresh backup and no concurrent writers.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db_config import database_url
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def forbidden(conn, query, code, params=None):
    try:
        with conn.begin_nested():
            conn.execute(text(query), params or {})
    except DBAPIError as error:
        require(getattr(error.orig, "sqlstate", None) == code, f"Wrong SQLSTATE for {query}")
    else:
        raise RuntimeError(f"Unexpectedly permitted: {query}")


def admin(query, database="postgres"):
    return subprocess.check_output([
        "runuser", "-u", "postgres", "--", "psql", "-X", "-qAt",
        "-v", "ON_ERROR_STOP=1", "-d", database, "-c", query,
    ], text=True).strip()


def main():
    engine = create_engine(database_url())
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            require(conn.execute(text("SELECT current_user")).scalar_one() == "bashgroup_app", "Not using runtime account")
            flags = conn.execute(text("SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user")).one()
            require(not any(flags), "Runtime has administrative privileges")
            require(conn.execute(text("SELECT count(*) FROM app.agents")).scalar_one() == 5, "Expected 5 agents")
            require(conn.execute(text("SELECT count(*) FROM app.materials")).scalar_one() == 21, "Expected 21 materials")
            require(conn.execute(text("SELECT count(*) FROM app.materials WHERE ingestion_status <> 'registered'")).scalar_one() == 0, "Do not claim AI ingestion")
            require(conn.execute(text("SELECT count(*) FROM app.companies WHERE identity_status='unverified'")).scalar_one() == 5, "Candidate statuses")
            agent, skill = conn.execute(text("SELECT agent_id,id FROM app.skill_versions")).one()
            run = conn.execute(text("""INSERT INTO app.runs(agent_id,skill_version_id,mode,question)
                VALUES (:agent,:skill,'on_demand','Rollback-only database verification') RETURNING id"""), {"agent": agent, "skill": skill}).scalar_one()
            report = conn.execute(text("""INSERT INTO app.reports(run_id,title,summary,body_markdown)
                VALUES (:run,'Verification','Test','Test') RETURNING id"""), {"run": run}).scalar_one()
            recommendation = conn.execute(text("""INSERT INTO app.recommendations(report_id,title,rationale,first_step,priority)
                VALUES (:report,'Test','Test','Test','medium') RETURNING id"""), {"report": report}).scalar_one()
            decision = conn.execute(text("""INSERT INTO app.decisions(recommendation_id,action,actor_label)
                VALUES (:id,'accepted','Database verification') RETURNING id"""), {"id": recommendation}).scalar_one()
            conn.execute(text("UPDATE app.reports SET summary='Changed' WHERE id=:id"), {"id": report})
            require(conn.execute(text("SELECT summary FROM app.reports WHERE id=:id"), {"id": report}).scalar_one() == "Changed", "Runtime UPDATE failed")
            conn.execute(text("DELETE FROM app.decisions WHERE id=:id"), {"id": decision})
            for query in (
                "CREATE TABLE app.forbidden_probe(id integer)",
                "CREATE SCHEMA forbidden_probe",
                "ALTER TABLE app.agents ADD COLUMN forbidden_probe integer",
                "TRUNCATE app.agents",
                "UPDATE app.alembic_version SET version_num='forbidden_probe'",
                "SET ROLE bashgroup_owner",
            ):
                forbidden(conn, query, "42501")
            forbidden(conn, "INSERT INTO app.reports(run_id,title,summary,body_markdown) VALUES (:run,'duplicate','x','x')", "23505", {"run": run})
            forbidden(conn, "INSERT INTO app.reports(run_id,title,summary,body_markdown) VALUES (:run,'orphan','x','x')", "23503", {"run": uuid4()})
            forbidden(conn, "INSERT INTO app.decisions(report_id,action,actor_label) VALUES (:id,'revision_requested','test')", "23514", {"id": report})
            forbidden(conn, "UPDATE app.runs SET status='completed' WHERE id=:id", "23514", {"id": run})
            other_agent = conn.execute(text("SELECT id FROM app.agents WHERE id<>:id LIMIT 1"), {"id": agent}).scalar_one()
            forbidden(conn, "INSERT INTO app.runs(agent_id,skill_version_id,mode) VALUES (:agent,:skill,'baseline')", "23503", {"agent": other_agent, "skill": skill})
            stored_skill, digest = conn.execute(text("SELECT instructions,sha256 FROM app.skill_versions")).one()
            require(hashlib.sha256(stored_skill.encode()).hexdigest() == digest, "Skill checksum")
        finally:
            tx.rollback()
    print("PASS runtime: CRUD with rollback, DDL/role/TRUNCATE denied, migration metadata protected, FK/unique/CHECK constraints, seed and skill integrity")

    backups = sorted(Path("/var/backups/bashgroup").glob("bashgroup-*.dump"))
    require(bool(backups), "No backup to verify")
    backup = backups[-1]
    database = "bashgroup_restorecheck_" + uuid4().hex[:16]
    tables = admin("SELECT tablename FROM pg_tables WHERE schemaname='app' ORDER BY tablename", "bashgroup").splitlines()

    def fingerprints(db):
        return {name: admin(
            f"SET timezone='UTC'; SELECT count(*)::text || ':' || md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),'')) FROM app.\"{name}\" t", db
        ) for name in tables}

    original = fingerprints("bashgroup")
    created = False
    try:
        admin(f'CREATE DATABASE "{database}" TEMPLATE template0')
        created = True
        subprocess.run([
            "runuser", "-u", "postgres", "--", "pg_restore", "--exit-on-error",
            "--no-owner", "--no-privileges", "--dbname", database, str(backup),
        ], check=True)
        require(fingerprints(database) == original, "Restored data differs from live DB; take a fresh backup without concurrent writers")
        constraints = "SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='app'"
        require(admin(constraints, database) == admin(constraints, "bashgroup"), "Restored constraints differ")
        print(f"PASS restore: {backup.name}; all {len(tables)} tables and contents match; constraints restored")
    finally:
        if created:
            admin(f'DROP DATABASE "{database}" WITH (FORCE)')
    print("PASS cleanup: disposable restored DB removed; runtime test data rolled back")


if __name__ == "__main__":
    main()
