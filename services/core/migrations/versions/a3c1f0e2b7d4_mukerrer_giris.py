"""mükerrer giriş: plaka başına tek açık oturum

Revision ID: a3c1f0e2b7d4
Revises: 778d04ce39cc
Create Date: 2026-11-09 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a3c1f0e2b7d4'
down_revision: str | None = '778d04ce39cc'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Aynı plakanın birden çok açık oturumu varsa bu adım hata verir; önce temizlenmeli
    op.create_index(
        'uq_session_open_plate',
        'sessions',
        ['plate'],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    op.drop_index('uq_session_open_plate', table_name='sessions')
