"""Agregar google event id a turnos

Revision ID: f8b2d91a6c40
Revises: e5a7c9d3f102
Create Date: 2026-06-04 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f8b2d91a6c40'
down_revision = 'e5a7c9d3f102'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('appointment', schema=None) as batch_op:
        batch_op.add_column(sa.Column('google_event_id', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('appointment', schema=None) as batch_op:
        batch_op.drop_column('google_event_id')
