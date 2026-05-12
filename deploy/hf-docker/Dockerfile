# Hugging Face Spaces Docker 配置
# 完整部署: FastAPI 后端 + Vue 前端 (通过 Nginx 代理)

FROM python:3.11-slim AS backend

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ ./backend/
COPY data/ ./data/

# 复制前端构建产物
COPY frontend/dist/ /app/frontend/dist/

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/nginx.conf

# 复制启动脚本
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# 创建必要目录
RUN mkdir -p /tmp/plasmid_designer/uploads /tmp/plasmid_designer/output \
    /var/log/nginx /var/run

# 设置环境变量
ENV PYTHONPATH=/app/backend
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# HF Spaces 要求的元数据标签
LABEL sdk="docker"

# 暴露端口 (HF Spaces 要求 7860)
EXPOSE 7860

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# 启动
CMD ["/app/start.sh"]
