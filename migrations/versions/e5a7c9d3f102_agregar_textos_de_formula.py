"""Agregar textos de formula

Revision ID: e5a7c9d3f102
Revises: d9f1b5c2e704
Create Date: 2026-05-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e5a7c9d3f102'
down_revision = 'd9f1b5c2e704'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('client', schema=None) as batch_op:
        batch_op.add_column(sa.Column('evaluation_formula_text_1', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('evaluation_formula_text_2', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('evaluation_formula_text_3', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('evaluation_formula_text_4', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('client', schema=None) as batch_op:
        batch_op.drop_column('evaluation_formula_text_4')
        batch_op.drop_column('evaluation_formula_text_3')
        batch_op.drop_column('evaluation_formula_text_2')
        batch_op.drop_column('evaluation_formula_text_1')
