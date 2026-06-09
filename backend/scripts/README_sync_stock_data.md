# 股票数据同步脚本使用说明

## 功能概述

本脚本使用 **Baostock** 数据源实现股票数据的拉取和同步，包括：

1. **拉取股票列表入库** - 获取A股所有股票代码和名称
2. **拉取历史交易数据** - 按股票代码获取过去一年的日线交易数据
3. **增量同步数据** - 后续只同步最新一天的数据

## 依赖安装

```bash
# 安装 Baostock
pip install baostock

# 安装其他依赖
pip install -r requirements.txt
```

## 使用方法

### 1. 首次运行 - 初始化同步

拉取所有股票列表 + 过去一年的交易数据：

```bash
cd E:/myproject/stock-v4/backend
python scripts/sync_stock_data.py --init
```

只拉取最近 180 天的数据：

```bash
python scripts/sync_stock_data.py --init --history 180
```

测试模式（只处理前 10 只股票）：

```bash
python scripts/sync_stock_data.py --init --limit 10
```

### 2. 增量同步 - 每日运行

只同步最新一天的数据（用于定时任务）：

```bash
python scripts/sync_stock_data.py --incremental
```

### 3. 只更新股票列表

当需要更新股票列表（如新股上市）时：

```bash
python scripts/sync_stock_data.py --update-list
```

### 4. 处理指定股票

只获取某只股票的历史数据：

```bash
# 获取平安银行（000001）过去一年的数据
python scripts/sync_stock_data.py --stock 000001

# 获取过去 180 天的数据
python scripts/sync_stock_data.py --stock 000001 --history 180
```

## 命令行参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--init` | 初始化同步：拉取股票列表 + 历史数据 | - |
| `--incremental` | 增量同步：只同步最新数据 | - |
| `--update-list` | 只更新股票列表 | - |
| `--stock` | 只处理指定股票代码 | None |
| `--history` | 获取最近多少天的历史数据 | 365 |
| `--limit` | 限制处理的股票数量（用于测试） | None |
| `--output` | 将股票列表保存到指定文件 | None |

## 数据库表结构

脚本使用以下数据库表：

### stocks 表（股票基础信息）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| stock_code | String(20) | 股票代码（如 000001） |
| stock_name | String(100) | 股票名称 |
| market | String(10) | 市场（SH/SZ） |
| industry | String(100) | 行业分类 |
| listing_date | Date | 上市日期 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### stock_daily 表（日线交易数据）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| stock_code | String(20) | 股票代码 |
| trade_date | Date | 交易日期 |
| open_price | DECIMAL(10,4) | 开盘价 |
| close_price | DECIMAL(10,4) | 收盘价 |
| high_price | DECIMAL(10,4) | 最高价 |
| low_price | DECIMAL(10,4) | 最低价 |
| volume | BigInteger | 成交量 |
| turnover | DECIMAL(15,2) | 成交额 |
| pe_ratio | DECIMAL(10,4) | 市盈率 |
| pb_ratio | DECIMAL(10,4) | 市净率 |
| created_at | DateTime | 创建时间 |

## 定时任务配置

可以使用 crontab（Linux/Mac）或任务计划程序（Windows）配置定时任务：

### Linux/Mac - crontab

```bash
# 每个交易日 16:30 执行增量同步
30 16 * * 1-5 cd /path/to/stock-v4/backend && python scripts/sync_stock_data.py --incremental

# 每周日凌晨 2:00 更新股票列表
0 2 * * 0 cd /path/to/stock-v4/backend && python scripts/sync_stock_data.py --update-list
```

### Windows - 任务计划程序

创建一个批处理文件 `sync_stock.bat`：

```batch
@echo off
cd /d E:\myproject\stock-v4\backend
python scripts/sync_stock_data.py --incremental
```

然后在任务计划程序中配置：
- 触发器：每个工作日 16:30
- 操作：运行 `sync_stock.bat`

## 数据获取说明

### 股票列表获取

使用 Baostock 的 `query_all_stock` 接口：

```python
# 需要传入一个近期交易日日期
rs = bs.query_all_stock(day="2024-06-06")
```

返回字段：
- `code`: 股票代码（如 sh.600000、sz.000001）
- `code_name`: 股票名称
- `tradeStatus`: 交易状态（1正常/0停牌）

### 历史交易数据获取

使用 Baostock 的 `query_history_k_data_plus` 接口：

```python
rs = bs.query_history_k_data_plus(
    code="sz.000001",
    fields="date,code,open,high,low,close,volume,amount,turn,pctChg",
    start_date="2023-06-09",
    end_date="2024-06-09",
    frequency="d",       # d=日线 w=周 m=月
    adjustflag="2"       # 1=后复权 2=前复权 3=不复权
)
```

返回字段：
- `date`: 日期
- `code`: 股票代码
- `open`: 开盘价
- `high`: 最高价
- `low`: 最低价
- `close`: 收盘价
- `volume`: 成交量
- `amount`: 成交额
- `turn`: 换手率
- `pctChg`: 涨跌幅

## 注意事项

1. **交易日选择**：获取股票列表时需要传入一个有效的交易日日期，否则可能返回空
2. **限频处理**：脚本内置了请求限频机制，避免被服务器限制
3. **数据去重**：使用 `UniqueConstraint` 确保同一股票同一交易日不会重复入库
4. **增量更新**：增量同步会自动跳过已存在的数据

## 故障排查

### 问题：获取股票列表失败

**解决方法**：
- 检查网络连接
- 确认 Baostock 已正确安装：`pip show baostock`
- 尝试使用固定的交易日日期

### 问题：历史数据获取失败

**解决方法**：
- 检查股票代码格式是否正确
- 确认日期范围内有交易数据（非交易日无数据）
- 查看日志了解详细错误信息

### 问题：数据库连接失败

**解决方法**：
- 检查 `config.py` 中的数据库配置
- 确认数据库服务正在运行
- 验证数据库用户权限

## 日志

脚本运行时会输出详细日志，包括：
- 当前同步进度
- 成功/失败的记录数
- 错误信息和警告

日志级别可以通过修改 `logging.basicConfig` 的 `level` 参数调整。
