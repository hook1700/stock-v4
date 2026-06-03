FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装，然后清理编译器减小镜像体积
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc

# 复制应用代码
COPY . .

# 创建非root用户运行，并确保日志目录有写入权限
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# 启动命令（workers 可通过环境变量调整）
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}"]
