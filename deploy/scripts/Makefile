# 项目根目录的 Makefile

.PHONY: help install dev build test clean docker-up docker-down

help:
	@echo "Plasmid Designer - 命令帮助"
	@echo ""
	@echo "开发命令:"
	@echo "  make install      - 安装所有依赖"
	@echo "  make dev          - 启动开发服务器"
	@echo "  make test         - 运行测试"
	@echo "  make clean        - 清理临时文件"
	@echo ""
	@echo "Docker命令:"
	@echo "  make docker-up    - 启动Docker服务"
	@echo "  make docker-down  - 停止Docker服务"
	@echo "  make docker-build - 构建Docker镜像"
	@echo ""
	@echo "部署命令:"
	@echo "  make build        - 构建生产版本"

# 安装依赖
install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

# 开发模式
dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

dev:
	@echo "启动后端服务..."
	@make dev-backend &
	@echo "启动前端服务..."
	@make dev-frontend

# 测试
test:
	cd backend && pytest tests/ -v

test-cov:
	cd backend && pytest tests/ -v --cov=core --cov-report=html

# 清理
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "node_modules" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.log" -delete

# Docker
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build

docker-logs:
	docker-compose logs -f

# 构建
build-backend:
	cd backend && pip wheel . -w dist/

build-frontend:
	cd frontend && npm run build

build:
	@make build-backend
	@make build-frontend
