# Plasmid Designer Backend

FastAPI 后端服务

## 安装

```bash
pip install -r ../requirements.txt
```

## 运行

```bash
# 开发模式
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 或直接运行
python main.py
```

## API 文档

启动后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 端点

### 设计任务

- `POST /api/design` - 创建设计任务
- `GET /api/design/{design_id}` - 查询设计结果
- `GET /api/design/{design_id}/download/genbank` - 下载 GenBank 文件
- `GET /api/design/{design_id}/download/primers` - 下载引物订单

### 载体库

- `GET /api/vectors` - 列出所有载体
- `GET /api/vectors/{vector_id}` - 获取载体详情

### 密码子表

- `GET /api/codon-tables` - 列出可用密码子表
