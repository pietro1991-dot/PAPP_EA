"""Autenticazione: registrazione gated da license key monouso, login con cookie
di sessione firmato (itsdangerous), hashing password con bcrypt (passlib).

I segnali restano condivisi: il multi-tenant qui riguarda solo account + cronologia
chat. Una license key vale per un solo account (anti-condivisione di base).
"""
import os
from datetime import datetime

from fastapi import Request, HTTPException
from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import select, func

from db import AsyncSession, User, LicenseKey

SECRET_KEY = os.getenv("SECRET_KEY", "")
COOKIE_NAME = "papp_session"
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", str(7 * 24 * 3600)))  # 7 giorni
# In produzione (dietro TLS) impostare COOKIE_SECURE=1: il cookie viaggia solo su HTTPS.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"

if not SECRET_KEY:
    # Fallback insicuro: va bene solo in sviluppo. In produzione impostare SECRET_KEY.
    import logging
    logging.getLogger("papp.auth").warning(
        "SECRET_KEY non impostata: uso una chiave di sviluppo insicura."
    )
    SECRET_KEY = "dev-insecure-change-me"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="papp-session")


class AuthError(Exception):
    def __init__(self, msg: str, status: int = 400):
        self.msg = msg
        self.status = status
        super().__init__(msg)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password, password_hash)
    except Exception:
        return False


def create_session_token(user_id: int) -> str:
    return _serializer.dumps({"uid": user_id})


def verify_session_token(token: str):
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data.get("uid")
    except (BadSignature, SignatureExpired):
        return None


async def register(email: str, password: str, license_key: str) -> int:
    email = (email or "").strip().lower()
    password = password or ""
    license_key = (license_key or "").strip()

    if not email or "@" not in email:
        raise AuthError("Email non valida")
    if len(password) < 8:
        raise AuthError("Password troppo corta (minimo 8 caratteri)")
    if not license_key:
        raise AuthError("Licenza obbligatoria")

    async with AsyncSession() as session:
        lk = (
            await session.execute(
                select(LicenseKey).where(LicenseKey.key == license_key)
            )
        ).scalar_one_or_none()
        if not lk or lk.revoked:
            raise AuthError("Licenza non valida")
        if lk.used_by_user_id is not None:
            raise AuthError("Licenza già utilizzata")

        exists = (
            await session.execute(select(User.id).where(User.email == email))
        ).scalar_one_or_none()
        if exists:
            raise AuthError("Email già registrata")

        user = User(
            email=email,
            password_hash=hash_password(password),
            license_key=lk.key,
        )
        session.add(user)
        await session.flush()  # popola user.id
        lk.used_by_user_id = user.id
        await session.commit()
        return user.id


async def login(email: str, password: str) -> int:
    email = (email or "").strip().lower()
    async with AsyncSession() as session:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            raise AuthError("Credenziali non valide", 401)
        user.last_login = datetime.utcnow()
        await session.commit()
        return user.id


async def current_user(request: Request) -> User:
    """Dependency FastAPI: ritorna lo User loggato o solleva 401."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Non autenticato")
    uid = verify_session_token(token)
    if not uid:
        raise HTTPException(status_code=401, detail="Sessione non valida")
    async with AsyncSession() as session:
        user = await session.get(User, uid)
    if not user:
        raise HTTPException(status_code=401, detail="Utente inesistente")
    return user
