"""Alembic ortamı. Sahip: Damla."""

from alembic import context
from sqlalchemy import engine_from_config, pool

from core.config import settings
from core.db import Base
from core.models import *  # noqa: F403  tüm tabloların metadata'ya kaydı için

config = context.config

# Veritabanı adresi alembic.ini'de DEĞİL, uygulamayla aynı kaynakta tutuluyor:
# ortam değişkeni → .env → core/config.py'deki varsayılan. İki yerde tekrarlanan
# adres ayrışır: .env'de POSTGRES_PORT değiştiğinde uygulama yeni porta giderken
# alembic eskisini arar ve hata sebebini söylemez (YOL_HARITASI §18, port çakışması).
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
