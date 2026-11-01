"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
## Mako koşul satırı çıktıya basılmaz: imports boşken fazladan boş satır oluşmaz.
## Düz ${imports if imports else ""} kullanılırsa her migration ruff I001 ile CI'ı kırar.
% if imports:
${imports}
% endif

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
