from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.service import authenticate, make_token_response, register
from app.core.database import get_db
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


import traceback

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_route(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await register(db, data)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}\nTraceback:\n{tb}"
        )
    return make_token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate(db, data.email, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return make_token_response(user)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
