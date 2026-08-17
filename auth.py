import os
import secrets
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserSession

load_dotenv()


password_hash = PasswordHash(
    (BcryptHasher(),)
)

SESSION_COOKIE_NAME = os.getenv(
    "SESSION_COOKIE_NAME",
    "session_id"
)

SESSION_EXPIRE_MINUTES = int(
    os.getenv(
        "SESSION_EXPIRE_MINUTES",
        "60"
    )
)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    password: str,
    password_hash_value: str
) -> bool:
    return password_hash.verify(
        password,
        password_hash_value
    )


def create_session(
    db: Session,
    user_id: int
) -> str:

    session_id = secrets.token_urlsafe(32)

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=SESSION_EXPIRE_MINUTES
        )
    )

    session = UserSession(
        id=session_id,
        user_id=user_id,
        expires_at=expires_at
    )

    db.add(session)
    db.commit()

    return session_id


def delete_session(
    db: Session,
    session_id: str
):
    session = (
        db.query(UserSession)
        .filter(UserSession.id == session_id)
        .first()
    )

    if session:
        db.delete(session)
        db.commit()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    session_id = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    if not session_id:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )

    session = (
        db.query(UserSession)
        .filter(
            UserSession.id == session_id
        )
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=401,
            detail="Invalid session"
        )

    now = datetime.now(timezone.utc)

    expires_at = session.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    if expires_at < now:
        db.delete(session)
        db.commit()

        raise HTTPException(
            status_code=401,
            detail="Session expired"
        )

    user = (
        db.query(User)
        .filter(User.id == session.user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user