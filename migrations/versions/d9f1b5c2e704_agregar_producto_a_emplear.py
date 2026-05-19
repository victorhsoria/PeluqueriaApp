"""Agregar producto a emplear

Revision ID: d9f1b5c2e704
Revises: c4e6a1f58d20
Create Date: 2026-05-18 12:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd9f1b5c2e704'
down_revision = 'c4e6a1f58d20'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('client', schema=None) as batch_op:
        batch_op.add_column(sa.Column('evaluation_product_to_use', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('client', schema=None) as batch_op:
        batch_op.drop_column('evaluation_product_to_use')
