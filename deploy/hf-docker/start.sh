#!/bin/bash
# Hugging Face Spaces Docker 启动脚本
# 同时运行 FastAPI 后端 (端口 8000) 和 Nginx 前端代理 (端口 7860)

set -e

# 创建必要目录
mkdir -p /tmp/plasmid_designer/uploads /tmp/plasmid_designer/output

# 启动 FastAPI 后端 (内部端口 8000)
cd /app
python3 -m uvicorn main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 1 \
    --log-level info &

BACKEND_PID=$!

# 等待后端就绪
echo "Waiting for backend to start..."
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
        echo "Backend is ready"
        break
    fi
    sleep 1
done

# 启动 Nginx (对外端口 7860)
echo "Starting Nginx on port 7860..."
nginx -g "daemon off;" &

NGINX_PID=$!

# 优雅关闭
cleanup() {
    echo "Shutting down..."
    kill $NGINX_PID 2>/dev/null || true
    kill $BACKEND_PID 2>/dev/null || true
    wait
}

trap cleanup SIGTERM SIGINT

# 保持运行
wait
