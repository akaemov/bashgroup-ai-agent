from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from db_config import database_url


if context.is_offline_mode():
    raise RuntimeError("Use online migrations against the configured database")

engine = create_engine(database_url("migrator"), poolclass=NullPool)
with engine.connect() as connection:
    connection.exec_driver_sql("SET ROLE bashgroup_owner")
    connection.commit()
    context.configure(
        connection=connection,
        version_table_schema="app",
        transactional_ddl=True,
    )
    with context.begin_transaction():
        context.run_migrations()
