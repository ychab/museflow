"""empty message

Revision ID: 7e443ad8cff3
Revises: b74d2db001d0
Create Date: 2026-05-26 16:10:34.698951

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e443ad8cff3'
down_revision: Union[str, Sequence[str], None] = 'b74d2db001d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_status_enum = sa.Enum('BUILDING', 'FINISHED', name='tasteprofilestatus')


def upgrade() -> None:
    """Upgrade schema."""
    _status_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'museflow_taste_profile',
        sa.Column('status', _status_enum, server_default='FINISHED', nullable=False),
    )
    op.execute(
        "UPDATE museflow_taste_profile SET status = 'BUILDING' WHERE checkpoint_profile IS NOT NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('museflow_taste_profile', 'status')
    _status_enum.drop(op.get_bind(), checkfirst=True)
