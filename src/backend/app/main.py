"""
Plasmid Designer - FastAPI 应用入口
精简版：仅包含 app 创建、中间件、路由挂载、启动事件
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

from app.config import settings
from app.storage import STORAGE_MODE

# ==================== 创建应用 ====================

app = FastAPI(
    title="Plasmid Designer API",
    description="自动化质粒构建设计平台 API",
    version="0.1.0"
)

# ==================== 中间件 ====================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境需要限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 根路径 & 健康检查 ====================

@app.get("/")
async def root():
    """API 根路径"""
    return {
        "name": "Plasmid Designer API",
        "version": "0.1.0",
        "status": "running",
        "storage_mode": STORAGE_MODE
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now(), "storage_mode": STORAGE_MODE}


# ==================== 挂载路由 ====================

from app.routes.design_routes import router as design_router
from app.routes.batch_routes import router as batch_router
from app.routes.vector_routes import router as vector_router
from app.routes.codon_routes import router as codon_router
from app.auth.routes import router as auth_router
from app.cache_routes import router as cache_router
from app.rate_limit_routes import router as rate_limit_router
from app.analysis_routes import router as analysis_router

app.include_router(design_router)
app.include_router(batch_router)
app.include_router(vector_router)
app.include_router(codon_router)
app.include_router(auth_router)
app.include_router(cache_router)
app.include_router(rate_limit_router)
app.include_router(analysis_router)

# 速率限制中间件
from app.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)


# ==================== 启动事件 ====================

@app.on_event("startup")
async def startup():
    """应用启动时初始化"""
    print(f"🧬 Plasmid Designer API v0.1.0")
    print(f"📦 Storage mode: {STORAGE_MODE}")

    # 数据库模式下初始化表
    if STORAGE_MODE == "database":
        try:
            from app.database import init_db
            init_db()
        except Exception as e:
            print(f"⚠️ 数据库初始化失败: {e}")


# ==================== 直接运行 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
