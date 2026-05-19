"""Agregar datos tecnicos de evaluacion

Revision ID: b2d8f4a9c731
Revises: a7c9e2d1b4f6
Create Date: 2026-05-18 12:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2d8f4a9c731'
down_revision = 'a7c9e2d1b4f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('client', schema=None) as batch_op:
        batch_op.add_column(sa.Column('evaluation_allergy_has', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('evaluation_allergy_detail', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('evaluation_gray_percentage', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('evaluation_growth', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('evaluation_desired_tone', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('evaluation_application_exposure', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('client', schema=None) as batch_op:
        batch_op.drop_column('evaluation_application_exposure')
        batch_op.drop_column('evaluation_desired_tone')
        batch_op.drop_column('evaluation_growth')
        batch_op.drop_column('evaluation_gray_percentage')
        batch_op.drop_column('evaluation_allergy_detail')
        batch_op.drop_column('evaluation_allergy_has')
