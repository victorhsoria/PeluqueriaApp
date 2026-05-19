"""Agregar evaluacion del cliente

Revision ID: a7c9e2d1b4f6
Revises: 4e809c2a199c
Create Date: 2026-05-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a7c9e2d1b4f6'
down_revision = '4e809c2a199c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('client', schema=None) as batch_op:
        batch_op.add_column(sa.Column('evaluation_hair_types', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('evaluation_textures', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('evaluation_scalp_conditions', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('evaluation_scalp_properties', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('evaluation_hair_loss', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('evaluation_dandruff', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('evaluation_formula_has_1', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('evaluation_formula_has_2', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('evaluation_formula_has_3', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('evaluation_formula_has_4', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('evaluation_formula_has_5', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('evaluation_formula_wants_1', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('evaluation_formula_wants_2', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('evaluation_formula_wants_3', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('evaluation_formula_wants_4', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('evaluation_formula_wants_5', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('evaluation_notes', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('client', schema=None) as batch_op:
        batch_op.drop_column('evaluation_notes')
        batch_op.drop_column('evaluation_formula_wants_5')
        batch_op.drop_column('evaluation_formula_wants_4')
        batch_op.drop_column('evaluation_formula_wants_3')
        batch_op.drop_column('evaluation_formula_wants_2')
        batch_op.drop_column('evaluation_formula_wants_1')
        batch_op.drop_column('evaluation_formula_has_5')
        batch_op.drop_column('evaluation_formula_has_4')
        batch_op.drop_column('evaluation_formula_has_3')
        batch_op.drop_column('evaluation_formula_has_2')
        batch_op.drop_column('evaluation_formula_has_1')
        batch_op.drop_column('evaluation_dandruff')
        batch_op.drop_column('evaluation_hair_loss')
        batch_op.drop_column('evaluation_scalp_properties')
        batch_op.drop_column('evaluation_scalp_conditions')
        batch_op.drop_column('evaluation_textures')
        batch_op.drop_column('evaluation_hair_types')
