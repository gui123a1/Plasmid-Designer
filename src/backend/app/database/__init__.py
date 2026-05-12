"""
数据库模块
"""

from .models import (
    Base, engine, SessionLocal, get_db, init_db, drop_db,
    UserDB, DesignDB, PrimerDB, DesignWarningDB, DesignErrorDB,
    BatchJobDB, BatchDesignDB, VectorDB, VectorFeatureDB
)
from .crud import (
    # 用户
    create_user, get_user_by_email, get_user_by_id, get_users,
    # 设计
    create_design, get_design, get_designs_by_user, update_design,
    add_primer, add_warning, add_error,
    # 批量
    create_batch_job, get_batch_job, update_batch_job, add_batch_design,
    # 载体
    create_vector, get_vector, get_vectors, delete_vector, add_vector_feature
)

__all__ = [
    # 模型
    "Base", "engine", "SessionLocal", "get_db", "init_db", "drop_db",
    "UserDB", "DesignDB", "PrimerDB", "DesignWarningDB", "DesignErrorDB",
    "BatchJobDB", "BatchDesignDB", "VectorDB", "VectorFeatureDB",
    # CRUD
    "create_user", "get_user_by_email", "get_user_by_id", "get_users",
    "create_design", "get_design", "get_designs_by_user", "update_design",
    "add_primer", "add_warning", "add_error",
    "create_batch_job", "get_batch_job", "update_batch_job", "add_batch_design",
    "create_vector", "get_vector", "get_vectors", "delete_vector", "add_vector_feature"
]
