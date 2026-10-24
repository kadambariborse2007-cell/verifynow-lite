"""
auth_routes.py - Register, login and "who am I".

POST /api/auth/register  -> customers only (staff are created by seed.py)
POST /api/auth/login     -> returns a JWT token, role and name
GET  /api/me             -> the logged-in user
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import create_access_token, get_current_user, hash_password, verify_password
from database import get_db
from models import User
from schemas import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    # Usernames are stored in lower case so "Rahul" and "rahul" are the same user
    username = data.username.lower()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken.")

    # Role is always "customer" here - nobody can register as staff
    user = User(
        name=data.name,
        username=username,
        password_hash=hash_password(data.password),
        role="customer",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/auth/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username.strip().lower()).first()
    # Same message for "no such user" and "wrong password" so attackers learn nothing
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

    return TokenOut(access_token=create_access_token(user), role=user.role, name=user.name)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
