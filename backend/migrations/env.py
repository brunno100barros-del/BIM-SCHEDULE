from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401  (registra as tabelas no metadata)
from app.core.config import get_settings
from app.core.database import Base

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Quando chamado pelo serviço, a URL já vem definida. Pela linha de comando
# (alembic upgrade head), resolve a pasta de dados da mesma forma que o serviço,
# incluindo a migração segura de dados legados, para nunca criar um banco vazio
# ao lado dos dados existentes.
if not config.attributes.get("url_resolved") and config.get_main_option("sqlalchemy.url", "").startswith("sqlite:///./"):
    from app.core.storage import resolve_storage

    layout = resolve_storage(get_settings())
    config.set_main_option("sqlalchemy.url", layout.database_url)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"}, compare_type=True, render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        # Não executar comandos antes de begin_transaction(): no SQLAlchemy 2 isso abre uma
        # transação implícita, o Alembic deixa de confirmá-la e TUDO o que a migração grava
        # (inclusive alembic_version) é desfeito ao fechar a conexão. As migrações rodam sem
        # PRAGMA foreign_keys (padrão do SQLite), recomendação do Alembic: evita exclusões em
        # cascata acidentais durante alterações de esquema.
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
