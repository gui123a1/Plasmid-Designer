"""数据库存储实现 — 封装 crud.py 的函数调用"""

from typing import Optional, List, Dict, Any
from datetime import datetime

from .base import DesignStoreBase, BatchStoreBase


class DBDesignStore(DesignStoreBase):
    """基于 SQLAlchemy 的设计存储"""

    def save(self, design_id: str, data: Dict[str, Any]) -> None:
        from app.database import SessionLocal, create_design as db_create_design
        db = SessionLocal()
        try:
            # 检查是否已存在
            from app.database.crud import get_design as db_get_design
            existing = db_get_design(db, design_id)
            if existing:
                # 更新
                db_get_design.__module__  # 确保 import 生效
                self.update(design_id, **data)
                return

            db_create_design(
                db,
                input_sequence=data.get("input_sequence", ""),
                sequence_type=data.get("sequence_type", "amino_acid"),
                sequence_name=data.get("sequence_name", "insert"),
                vector_id=data.get("vector_id", "pET-28a"),
                cloning_method=data.get("cloning_method", "gibson"),
            )
        finally:
            db.close()

    def get(self, design_id: str) -> Optional[Dict[str, Any]]:
        from app.database import SessionLocal
        from app.database.crud import get_design as db_get_design
        db = SessionLocal()
        try:
            design = db_get_design(db, design_id)
            if not design:
                return None
            return self._db_to_dict(design)
        finally:
            db.close()

    def update(self, design_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        from app.database import SessionLocal
        from app.database.crud import update_design as db_update_design
        db = SessionLocal()
        try:
            design = db_update_design(db, design_id, **kwargs)
            if not design:
                return None
            return self._db_to_dict(design)
        finally:
            db.close()

    def exists(self, design_id: str) -> bool:
        from app.database import SessionLocal
        from app.database.crud import get_design as db_get_design
        db = SessionLocal()
        try:
            return db_get_design(db, design_id) is not None
        finally:
            db.close()

    def add_primer(self, design_id: str, primer_data: Dict[str, Any]) -> None:
        from app.database import SessionLocal
        from app.database.crud import add_primer as db_add_primer
        db = SessionLocal()
        try:
            db_add_primer(
                db,
                design_id=design_id,
                name=primer_data.get("name", ""),
                sequence=primer_data.get("sequence", ""),
                full_sequence=primer_data.get("full_sequence", ""),
                tm=primer_data.get("tm", 0.0),
                gc_content=primer_data.get("gc_content", 0.0),
                length=primer_data.get("length", 0),
                overhang=primer_data.get("overhang"),
                notes=primer_data.get("notes")
            )
        finally:
            db.close()

    def add_warning(self, design_id: str, message: str) -> None:
        from app.database import SessionLocal
        from app.database.crud import add_warning as db_add_warning
        db = SessionLocal()
        try:
            db_add_warning(db, design_id, message)
        finally:
            db.close()

    def add_error(self, design_id: str, message: str) -> None:
        from app.database import SessionLocal
        from app.database.crud import add_error as db_add_error
        db = SessionLocal()
        try:
            db_add_error(db, design_id, message)
        finally:
            db.close()

    def list_designs(self, skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        from app.database import SessionLocal
        from app.database.models import DesignDB
        db = SessionLocal()
        try:
            designs = db.query(DesignDB).offset(skip).limit(limit).all()
            return [self._db_to_dict(d) for d in designs]
        finally:
            db.close()

    def _db_to_dict(self, design) -> Dict[str, Any]:
        """将 ORM 对象转换为字典"""
        return {
            "design_id": design.id,
            "status": design.status,
            "input_sequence": design.input_sequence,
            "optimized_sequence": design.optimized_sequence,
            "cai": design.cai,
            "gc_content": design.gc_content,
            "vector_id": design.vector_id,
            "cloning_method": design.cloning_method,
            "final_length": design.final_length,
            "validation_passed": design.validation_passed,
            "created_at": design.created_at,
            "completed_at": design.completed_at,
            "primers": [
                {
                    "name": p.name,
                    "sequence": p.sequence,
                    "full_sequence": p.full_sequence,
                    "tm": p.tm,
                    "gc_content": p.gc_content,
                    "length": p.length,
                    "overhang": p.overhang,
                    "notes": p.notes
                }
                for p in (design.primers or [])
            ],
            "warnings": [w.message for w in (design.warnings or [])],
            "errors": [e.message for e in (design.errors or [])],
        }


class DBBatchStore(BatchStoreBase):
    """基于 SQLAlchemy 的批量任务存储"""

    def save(self, batch_id: str, data: Dict[str, Any]) -> None:
        from app.database import SessionLocal
        from app.database.crud import create_batch_job as db_create_batch
        db = SessionLocal()
        try:
            existing = db.query(
                __import__('app.database.models', fromlist=['BatchJobDB']).BatchJobDB
            ).filter_by(id=batch_id).first()
            if existing:
                return
            db_create_batch(db, total=data.get("total", 0))
        finally:
            db.close()

    def get(self, batch_id: str) -> Optional[Dict[str, Any]]:
        from app.database import SessionLocal
        from app.database.crud import get_batch_job as db_get_batch
        db = SessionLocal()
        try:
            batch = db_get_batch(db, batch_id)
            if not batch:
                return None
            return self._db_to_dict(batch)
        finally:
            db.close()

    def update(self, batch_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        from app.database import SessionLocal
        from app.database.crud import update_batch_job as db_update_batch
        db = SessionLocal()
        try:
            batch = db_update_batch(db, batch_id, **kwargs)
            if not batch:
                return None
            return self._db_to_dict(batch)
        finally:
            db.close()

    def exists(self, batch_id: str) -> bool:
        from app.database import SessionLocal
        from app.database.crud import get_batch_job as db_get_batch
        db = SessionLocal()
        try:
            return db_get_batch(db, batch_id) is not None
        finally:
            db.close()

    def add_result(self, batch_id: str, design_id: str) -> None:
        from app.database import SessionLocal
        from app.database.crud import add_batch_design as db_add_batch_design
        db = SessionLocal()
        try:
            db_add_batch_design(db, batch_id, design_id)
        finally:
            db.close()

    def add_error(self, batch_id: str, error_data: Dict[str, Any]) -> None:
        # 在数据库模式下，错误存储在批量任务的 errors 字段
        # 简化实现：记录到日志或扩展模型
        pass

    def increment_completed(self, batch_id: str) -> None:
        from app.database import SessionLocal
        from app.database.crud import get_batch_job as db_get_batch, update_batch_job as db_update_batch
        db = SessionLocal()
        try:
            batch = db_get_batch(db, batch_id)
            if batch:
                db_update_batch(db, batch_id, completed=batch.completed + 1)
        finally:
            db.close()

    def increment_failed(self, batch_id: str) -> None:
        from app.database import SessionLocal
        from app.database.crud import get_batch_job as db_get_batch, update_batch_job as db_update_batch
        db = SessionLocal()
        try:
            batch = db_get_batch(db, batch_id)
            if batch:
                db_update_batch(db, batch_id, failed=batch.failed + 1)
        finally:
            db.close()

    def _db_to_dict(self, batch) -> Dict[str, Any]:
        """将 ORM 对象转换为字典"""
        return {
            "batch_id": batch.id,
            "total": batch.total,
            "completed": batch.completed,
            "failed": batch.failed,
            "status": batch.status,
            "results": [bd.design_id for bd in (batch.design_ids or [])],
            "errors": [],
        }
