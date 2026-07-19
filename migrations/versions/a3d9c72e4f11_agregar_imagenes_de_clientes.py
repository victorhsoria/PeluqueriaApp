"""Agregar imagenes de clientes

Revision ID: a3d9c72e4f11
Revises: f8b2d91a6c40
Create Date: 2026-07-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a3d9c72e4f11'
down_revision = 'f8b2d91a6c40'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'client_image',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['client.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('client_image')
