from pathlib import Path
from logging.config import fileConfig

from flask import current_app
from alembic import context

config = context.config
if config.config_file_name and Path(config.config_file_name).exists():
    fileConfig(config.config_file_name)
target_metadata = current_app.extensions['migrate'].db.metadata


def get_engine():
    return current_app.extensions['migrate'].db.get_engine()


def get_url():
    return str(get_engine().url).replace('%', '%%')


def run_migrations_offline():
    context.configure(url=get_url(), target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connection = get_engine().connect()
    try:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True, compare_server_default=True)
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
