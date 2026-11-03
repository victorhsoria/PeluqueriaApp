"""Recordar equivalencias entre listas de precios y productos.

Revision ID: d6e9f4a1c832
Revises: c5d8e3f0b721
"""
from alembic import op
import sqlalchemy as sa

revision = 'd6e9f4a1c832'
down_revision = 'c5d8e3f0b721'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('product_price_link',
        sa.Column('source_key', sa.String(64), primary_key=True),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('product.id'), nullable=False))
    op.create_index('ix_product_price_link_product_id', 'product_price_link', ['product_id'])


def downgrade():
    op.drop_index('ix_product_price_link_product_id', table_name='product_price_link')
    op.drop_table('product_price_link')
