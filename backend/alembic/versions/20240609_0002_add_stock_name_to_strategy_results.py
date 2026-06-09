"""为strategy_results表添加stock_name字段

修订号: 0002
创建时间: 2026-06-09 15:11:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 为 strategy_results 表添加 stock_name 字段
    op.add_column('strategy_results', sa.Column('stock_name', sa.String(length=100), nullable=True))
    op.create_index('ix_strategy_results_stock_name', 'strategy_results', ['stock_name'], unique=False)


def downgrade() -> None:
    # 回滚：删除 stock_name 字段
    op.drop_index('ix_strategy_results_stock_name', table_name='strategy_results')
    op.drop_column('strategy_results', 'stock_name')
