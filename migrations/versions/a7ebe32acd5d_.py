"""Add blacklist tables for artists and tracks

Revision ID: a7ebe32acd5d
Revises: 10cfb105a1b5
Create Date: 2026-05-27 12:09:35.247178

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7ebe32acd5d'
down_revision: Union[str, Sequence[str], None] = '10cfb105a1b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('museflow_blacklisted_artist',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('artist_name', sa.String(length=512), nullable=False),
    sa.Column('fingerprint', sa.String(length=512), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['museflow_user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'fingerprint', name='uq_museflow_blacklisted_artist_user_fp')
    )
    op.create_table('museflow_blacklisted_track',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=512), nullable=False),
    sa.Column('artist_name', sa.String(length=512), nullable=False),
    sa.Column('fingerprint', sa.String(length=512), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['museflow_user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'fingerprint', name='uq_museflow_blacklisted_track_user_fp')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('museflow_blacklisted_track')
    op.drop_table('museflow_blacklisted_artist')
