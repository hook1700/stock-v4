"""初始数据库架构 - 创建核心表

修订号: 0001
创建时间: 2024-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 stocks 表
    op.create_table(
        'stocks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_code', sa.String(length=20), nullable=False),
        sa.Column('stock_name', sa.String(length=100), nullable=False),
        sa.Column('market', sa.String(length=10), nullable=True),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('listing_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', name='uix_stock_code')
    )
    op.create_index('ix_stocks_stock_code', 'stocks', ['stock_code'], unique=False)

    # 创建 stock_daily 表
    op.create_table(
        'stock_daily',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stock_code', sa.String(length=20), nullable=False),
        sa.Column('trade_date', sa.Date(), nullable=False),
        sa.Column('open_price', sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column('close_price', sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column('high_price', sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column('low_price', sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column('volume', sa.BigInteger(), nullable=True),
        sa.Column('turnover', sa.DECIMAL(precision=15, scale=2), nullable=True),
        sa.Column('pe_ratio', sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column('pb_ratio', sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stock_code', 'trade_date', name='uix_stock_daily')
    )
    op.create_index('ix_stock_daily_stock_code', 'stock_daily', ['stock_code'], unique=False)
    op.create_index('ix_stock_daily_trade_date', 'stock_daily', ['trade_date'], unique=False)

    # 创建 strategies 表
    op.create_table(
        'strategies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建 strategy_results 表
    op.create_table(
        'strategy_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('stock_code', sa.String(length=20), nullable=False),
        sa.Column('trade_date', sa.Date(), nullable=False),
        sa.Column('signal_type', sa.String(length=20), nullable=True),
        sa.Column('buy_price', sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column('stop_loss', sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column('take_profit', sa.DECIMAL(precision=10, scale=4), nullable=True),
        sa.Column('confidence_score', sa.DECIMAL(precision=5, scale=4), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('strategy_id', 'stock_code', 'trade_date', name='uix_strategy_result')
    )
    op.create_index('ix_strategy_results_strategy_id', 'strategy_results', ['strategy_id'], unique=False)
    op.create_index('ix_strategy_results_trade_date', 'strategy_results', ['trade_date'], unique=False)

    # 创建 strategy_execution_logs 表
    op.create_table(
        'strategy_execution_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('trade_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), default='pending'),
        sa.Column('stocks_count', sa.Integer(), default=0),
        sa.Column('results_count', sa.Integer(), default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建 data_updates 表
    op.create_table(
        'data_updates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('update_type', sa.String(length=50), nullable=False),
        sa.Column('update_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), default='pending'),
        sa.Column('records_updated', sa.Integer(), default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_data_updates_update_date', 'data_updates', ['update_date'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_data_updates_update_date', table_name='data_updates')
    op.drop_table('data_updates')
    op.drop_table('strategy_execution_logs')
    op.drop_index('ix_strategy_results_trade_date', table_name='strategy_results')
    op.drop_index('ix_strategy_results_strategy_id', table_name='strategy_results')
    op.drop_table('strategy_results')
    op.drop_table('strategies')
    op.drop_index('ix_stock_daily_trade_date', table_name='stock_daily')
    op.drop_index('ix_stock_daily_stock_code', table_name='stock_daily')
    op.drop_table('stock_daily')
    op.drop_index('ix_stocks_stock_code', table_name='stocks')
    op.drop_table('stocks')
