"""
用户认证 API 路由（数据库版本）
统一使用数据库存储，prefix=/api/auth
"""

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from .jwt_auth import (
    UserCreate, UserLogin, User, Token,
    verify_password, create_access_token, hash_password,
    get_current_user, get_current_user_required, db_user_to_user
)
from app.database import get_db, get_users, create_user as db_create_user, get_user_by_email

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=Token)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    用户注册

    - 验证邮箱唯一性
    - 验证密码匹配
    - 创建用户账户
    - 返回认证令牌
    """
    # 检查邮箱是否已注册
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已注册"
        )

    # 验证密码
    if user_data.password != user_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="两次输入的密码不一致"
        )

    # 密码强度检查
    if len(user_data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码长度至少8位"
        )

    # 创建用户
    hashed_pw = hash_password(user_data.password)
    db_user = db_create_user(
        db=db,
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_pw
    )

    user = db_user_to_user(db_user)

    # 生成令牌
    access_token = create_access_token(user)

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=24 * 3600,
        user=user
    )


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    用户登录

    - 验证邮箱和密码
    - 返回认证令牌
    """
    # 查找用户
    user = get_user_by_email(db, credentials.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误"
        )

    # 验证密码
    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误"
        )

    # 检查用户状态
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用"
        )

    # 生成令牌
    user_response = db_user_to_user(user)
    access_token = create_access_token(user_response)

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=24 * 3600,
        user=user_response
    )


@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user_required)):
    """获取当前用户信息"""
    return current_user


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user_required)):
    """
    用户登出

    注意：JWT 是无状态的，真正的登出需要服务端维护黑名单
    这里只返回成功消息，客户端应删除本地令牌
    """
    return {"message": "登出成功"}


@router.get("/verify")
async def verify_token(current_user: User = Depends(get_current_user)):
    """
    验证令牌有效性

    - 返回用户信息如果令牌有效
    - 返回 null 如果令牌无效或未提供
    """
    if current_user:
        return {"valid": True, "user": current_user}
    return {"valid": False, "user": None}


@router.get("/users", response_model=list[User])
async def list_users(
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """列出所有用户（管理员）"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )

    users = get_users(db)
    return [db_user_to_user(u) for u in users]
