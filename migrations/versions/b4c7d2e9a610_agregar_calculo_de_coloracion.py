"""Guardar el calculo de costos de coloracion por trabajo.

Revision ID: b4c7d2e9a610
Revises: a3d9c72e4f11
"""
from alembic import op
import sqlalchemy as sa


revision = 'b4c7d2e9a610'
down_revision = 'a3d9c72e4f11'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('service', sa.Column('cost_breakdown', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('service', 'cost_breakdown')
