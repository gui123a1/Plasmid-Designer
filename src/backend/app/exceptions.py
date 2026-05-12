"""
异常处理模块
自定义异常类和全局异常处理器
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Dict, Any, Optional
import traceback
import logging

logger = logging.getLogger("plasmid_designer.errors")


# ==================== 自定义异常 ====================

class PlasmidDesignerError(Exception):
    """基础异常类"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class SequenceValidationError(PlasmidDesignerError):
    """序列验证错误"""
    
    def __init__(self, message: str, sequence: str = None, position: int = None):
        details = {}
        if sequence:
            details["sequence_preview"] = sequence[:50] + "..." if len(sequence) > 50 else sequence
        if position is not None:
            details["position"] = position
        
        super().__init__(
            message=message,
            error_code="SEQUENCE_VALIDATION_ERROR",
            details=details
        )


class VectorNotFoundError(PlasmidDesignerError):
    """载体未找到错误"""
    
    def __init__(self, vector_id: str):
        super().__init__(
            message=f"Vector not found: {vector_id}",
            error_code="VECTOR_NOT_FOUND",
            details={"vector_id": vector_id}
        )


class DesignError(PlasmidDesignerError):
    """设计任务错误"""
    
    def __init__(self, message: str, design_id: str = None, stage: str = None):
        details = {}
        if design_id:
            details["design_id"] = design_id
        if stage:
            details["stage"] = stage
        
        super().__init__(
            message=message,
            error_code="DESIGN_ERROR",
            details=details
        )


class PrimerDesignError(PlasmidDesignerError):
    """引物设计错误"""
    
    def __init__(self, message: str, sequence_length: int = None):
        details = {"sequence_length": sequence_length} if sequence_length else {}
        
        super().__init__(
            message=message,
            error_code="PRIMER_DESIGN_ERROR",
            details=details
        )


class AuthenticationError(PlasmidDesignerError):
    """认证错误"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR"
        )


class AuthorizationError(PlasmidDesignerError):
    """授权错误"""
    
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR"
        )


class RateLimitError(PlasmidDesignerError):
    """速率限制错误"""
    
    def __init__(self, retry_after: int = 60):
        super().__init__(
            message=f"Rate limit exceeded. Retry after {retry_after} seconds",
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after}
        )


class ExternalServiceError(PlasmidDesignerError):
    """外部服务错误"""
    
    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"External service error ({service}): {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            details={"service": service}
        )


# ==================== 异常处理器 ====================

async def plasmid_designer_exception_handler(
    request: Request,
    exc: PlasmidDesignerError
) -> JSONResponse:
    """自定义异常处理器"""
    
    logger.error(
        f"PlasmidDesigner Error: {exc.error_code} - {exc.message}",
        extra={"details": exc.details}
    )
    
    status_code = 400
    if isinstance(exc, AuthenticationError):
        status_code = 401
    elif isinstance(exc, AuthorizationError):
        status_code = 403
    elif isinstance(exc, (VectorNotFoundError,)):
        status_code = 404
    elif isinstance(exc, RateLimitError):
        status_code = 429
    
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException
) -> JSONResponse:
    """HTTP 异常处理器"""
    
    logger.warning(
        f"HTTP {exc.status_code}: {exc.detail}",
        extra={"path": str(request.url.path)}
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail)
            }
        }
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """请求验证异常处理器"""
    
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        f"Validation Error: {len(errors)} errors",
        extra={"errors": errors, "path": str(request.url.path)}
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": errors}
            }
        }
    )


async def general_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """通用异常处理器"""
    
    logger.error(
        f"Unexpected Error: {type(exc).__name__}: {str(exc)}",
        exc_info=True,
        extra={"path": str(request.url.path)}
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {}
            }
        }
    )


def register_exception_handlers(app):
    """注册异常处理器到 FastAPI 应用"""
    
    app.add_exception_handler(PlasmidDesignerError, plasmid_designer_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Exception handlers registered")
