"""Agregar configuraciones reutilizables de servicios.

Revision ID: c5d8e3f0b721
Revises: b4c7d2e9a610
"""
from alembic import op
import sqlalchemy as sa

revision = 'c5d8e3f0b721'
down_revision = 'b4c7d2e9a610'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('service_template',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(150), nullable=False, unique=True),
        sa.Column('pricing', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False))


def downgrade():
    op.drop_table('service_template')
