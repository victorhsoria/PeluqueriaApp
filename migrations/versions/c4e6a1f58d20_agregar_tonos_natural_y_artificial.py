"""Agregar tonos natural y artificial

Revision ID: c4e6a1f58d20
Revises: b2d8f4a9c731
Create Date: 2026-05-18 12:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c4e6a1f58d20'
down_revision = 'b2d8f4a9c731'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('client', schema=None) as batch_op:
        batch_op.add_column(sa.Column('evaluation_natural_tone', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('evaluation_artificial_tone', sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table('client', schema=None) as batch_op:
        batch_op.drop_column('evaluation_artificial_tone')
        batch_op.drop_column('evaluation_natural_tone')
