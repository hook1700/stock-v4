# 股票智能分析系统

基于 FastAPI + Vue3 + Element Plus 的多策略股票筛选分析平台。

## 功能特性

- **9大核心策略**: 短线×3 + 中线×3 + 长线×3
- **双数据源**: BaoStock + AKShare 数据适配
- **自动调度**: 每日17:45自动执行策略分析
- **Web管理界面**: 股票列表、策略结果、每日记录
- **Docker部署**: 一键部署到云服务器

## 技术栈

| 层级      | 技术                                         |
| --------- | -------------------------------------------- |
| 后端      | FastAPI, SQLAlchemy, PostgreSQL, APScheduler |
| 前端      | Vue3, Vite, Element Plus, Pinia, Axios       |
| 数据      | BaoStock, AKShare, Pandas                    |
| 部署      | Docker, Docker Compose, Nginx                |
| CI/CD     | GitHub Actions                               |

## 快速开始

### 本地开发

```bash
# 1. 复制环境变量
cp .env.example .env

# 2. 一键启动（后端+前端+数据库）
./deploy/start-local.sh

# 3. 访问
# 前端: http://localhost:3000
# API文档: http://localhost:8000/docs
```

### Docker 部署

```bash
# 1. 复制并编辑环境变量
cp .env.example .env

# 2. 启动所有服务
docker-compose up -d

# 3. 访问
# 前端: http://localhost
# API: http://localhost:8000
```

### 腾讯云部署

```bash
# 配置环境变量
export TENCENT_CLOUD_IP=你的服务器IP
export TENCENT_CLOUD_KEY=~/.ssh/your_key.pem

# 一键部署
./deploy/tencentcloud-deploy.sh
```

## 项目结构

```
stock-v4/
├── backend/            # FastAPI 后端
│   ├── api/           # API 路由
│   ├── models/        # 数据库模型
│   ├── services/      # 业务服务
│   ├── strategies/    # 策略实现
│   ├── data_sources/  # 数据源适配
│   ├── tests/         # 单元测试
│   └── Dockerfile
├── frontend/          # Vue3 前端
│   ├── src/
│   │   ├── api/      # 请求模块
│   │   ├── views/    # 页面组件
│   │   ├── store/    # Pinia 状态
│   │   └── router/   # 路由配置
│   └── Dockerfile
├── deploy/            # 部署脚本
├── docker-compose.yml
└── .env.example
```

## 策略体系

| 类型 | 策略名称             | 说明                  |
| ---- | -------------------- | --------------------- |
| 短线 | 均线回踩低吸         | 5/10日均线回踩买入    |
| 短线 | 突破缩量回踩         | 放量突破后缩量回调    |
| 短线 | 强势股10日线反抽     | 强势股10日线支撑     |
| 中线 | 行业成长+均线多头    | 成长行业均线多头排列  |
| 中线 | 困境反转             | 业绩改善+底部放量     |
| 中线 | 高股息红利           | 高股息率筛选         |
| 长线 | 优质白马龙头         | ROE+品牌护城河        |
| 长线 | 红利再投收息         | 持续分红策略          |
| 长线 | PEG低吸成长          | PEG<1成长股          |

## API 文档

启动后端后访问: http://localhost:8000/docs

主要接口:
- `GET /api/stocks/` - 股票列表
- `GET /api/strategies/` - 策略列表
- `POST /api/strategies/execute` - 执行策略
- `GET /api/daily-records/` - 每日记录
- `GET /api/system/status` - 系统状态

## 数据库迁移

```bash
cd backend

# 初始化迁移
alembic init alembic

# 创建新迁移
alembic revision --autogenerate -m "描述"

# 执行迁移
alembic upgrade head
```

## 许可证

MIT License
